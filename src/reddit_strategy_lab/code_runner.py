"""Bounded JSON IPC to a fail-closed macOS Seatbelt worker; no local-exec fallback."""

import json
import os
import platform
import selectors
import subprocess
import sys
import sysconfig
import threading
import time
from pathlib import Path

from .code_worker import BOOTSTRAP

MAX_MESSAGE = 65536


class RunnerError(ValueError):
    pass


def python_executable():
    framework = Path(sys.base_prefix) / "Resources/Python.app/Contents/MacOS/Python"
    return framework if framework.is_file() else Path(sys.executable).resolve()


def sandbox_profile():
    if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise RunnerError("custom code requires the supported macOS sandbox backend; no unsafe fallback")
    runtime = Path(sys.base_prefix).resolve()
    executable = python_executable()
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    # Do not grant any user/project directory or inherit the host virtualenv.
    if not str(runtime).startswith(("/Library/Frameworks/", "/opt/homebrew/", "/usr/local/")):
        raise RunnerError("Python runtime location has not been approved for sandbox isolation")

    def quoted(p):
        return json.dumps(str(p))

    return f"""(version 1)
(deny default)
(allow process-exec (literal {quoted(executable)}))
(allow file-read-metadata)
(allow file-read* (literal "/"))
(allow file-read* (subpath "/System/Library") (subpath "/usr/lib")
    (subpath {quoted(runtime)}) (literal "/dev/null") (literal "/dev/urandom")
    (literal "/dev/random") (literal "/private/etc/localtime"))
(deny file-read* (subpath {quoted(stdlib / "site-packages")}))
"""


class CodeRunner:
    def __init__(self, source, parameters, timeout=2.0):
        if not isinstance(source, str) or len(source.encode()) > 100000:
            raise RunnerError("strategy source exceeds 100000 bytes")
        if not 0 < timeout <= 10:
            raise RunnerError("invalid callback deadline")
        self.timeout = timeout
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.process = None
        self.stop_monitor = threading.Event()
        self.monitor = None
        try:
            self.process = subprocess.Popen(
                [
                    "/usr/bin/sandbox-exec",
                    "-p",
                    sandbox_profile(),
                    str(python_executable()),
                    "-s",
                    "-P",
                    "-S",
                    "-u",
                    "-c",
                    BOOTSTRAP,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd="/",
                env={"LC_ALL": "C", "PYTHONHASHSEED": "0"},
                close_fds=True,
                start_new_session=True,
            )
            self.monitor = threading.Thread(target=self._monitor, daemon=True)
            self.monitor.start()
            os.set_blocking(self.process.stdout.fileno(), False)
            os.set_blocking(self.process.stdin.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self._send({"source": source, "parameters": parameters}, limit=262144)
            if self._receive() != {"ready": True}:
                raise RunnerError("worker initialization failed")
        except BaseException:
            self.close()
            raise

    def _monitor(self):
        # macOS does not provide a reliable RLIMIT_AS. Sample RSS as an additional
        # best-effort guard, not a hard allocation boundary or production guarantee.
        while not self.stop_monitor.wait(0.1):
            if self.process.poll() is not None:
                return
            try:
                sample = subprocess.run(
                    ["/bin/ps", "-o", "rss=", "-p", str(self.process.pid)],
                    capture_output=True,
                    timeout=1,
                    check=True,
                )
                if int(sample.stdout.strip()) > 524288:
                    self.process.kill()
                    return
            except (OSError, ValueError, subprocess.SubprocessError):
                if self.process.poll() is None:
                    self.process.kill()
                return

    def _send(self, value, limit=MAX_MESSAGE):
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(data) > limit:
            raise RunnerError("worker input size limit exceeded")
        deadline = time.monotonic() + self.timeout
        with selectors.DefaultSelector() as writable:
            writable.register(self.process.stdin, selectors.EVENT_WRITE)
            offset = 0
            while offset < len(data):
                if not writable.select(max(0, deadline - time.monotonic())):
                    raise RunnerError("worker input deadline exceeded")
                try:
                    offset += os.write(self.process.stdin.fileno(), data[offset:])
                except BrokenPipeError:
                    raise RunnerError("worker exited") from None

    def _receive(self):
        deadline = time.monotonic() + self.timeout
        while b"\n" not in self.buffer:
            if not self.selector.select(max(0, deadline - time.monotonic())):
                raise RunnerError("worker callback deadline exceeded")
            chunk = os.read(self.process.stdout.fileno(), 8192)
            if not chunk:
                raise RunnerError("worker exited without a response")
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_MESSAGE:
                raise RunnerError("worker output size limit exceeded")
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        try:
            result = json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError):
            raise RunnerError("invalid worker JSON") from None
        if not isinstance(result, dict) or "error" in result:
            raise RunnerError("strategy failed inside worker")
        return result

    def step(self, event, portfolio):
        self._send({"event": event, "portfolio": portfolio})
        result = self._receive()
        if set(result) != {"sequence", "commands"} or type(result["sequence"]) is not int:
            raise RunnerError("invalid worker response envelope")
        if result["sequence"] != event["sequence"]:
            raise RunnerError("worker response sequence mismatch")
        return result["commands"]

    def close(self):
        self.stop_monitor.set()
        if self.monitor is not None:
            self.monitor.join(timeout=2)
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()
        self.selector.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def verify_sandbox():
    """Exercise actual denied operations before accepting a run, with no secrets."""
    import socket
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rsl-boundary-") as directory:
        sentinel = Path(directory) / "not-visible"
        sentinel.write_text("isolation probe, not a credential")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            source = """
import os, socket
class Strategy:
    def __init__(self, parameters):
        self.p = parameters
    def on_event(self, event, portfolio):
        denied = []
        for operation in (
            lambda: open(self.p['file']).read(),
            lambda: open(self.p['file'] + '-write', 'w'),
            lambda: socket.create_connection(('127.0.0.1', self.p['port']), timeout=.2),
            lambda: os.fork(),
        ):
            try:
                result = operation()
                if result == 0:
                    os._exit(0)
                denied.append(False)
            except PermissionError:
                denied.append(True)
        return denied + [not any(k in os.environ for k in ('HOME', 'RSL_CREDENTIALS_FILE'))]
"""
            with CodeRunner(source, {"file": str(sentinel), "port": listener.getsockname()[1]}) as worker:
                result = worker.step({"sequence": 0}, {})
            if result != [True] * 5:
                raise RunnerError("sandbox boundary probe failed; execution disabled")
    return {
        "backend": "macos-seatbelt",
        "file_read": "denied",
        "file_write": "denied",
        "network": "denied",
        "fork": "denied",
        "credentials": "not inherited",
        "memory_limit": "512MiB RSS sampling; best effort, not hard isolation",
    }
