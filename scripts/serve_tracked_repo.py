#!/usr/bin/env python3
"""Serve a local, clickable view of Git-tracked files only.

This intentionally does not expose ignored research inputs, credentials, or
the .git directory. It is a convenience viewer for the repository itself.
"""

from __future__ import annotations

import argparse
import html
import mimetypes
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def tracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def build_tree(paths: set[str]) -> dict[str, object]:
    tree: dict[str, object] = {}
    for path in sorted(paths):
        current = tree
        parts = PurePosixPath(path).parts
        for part in parts[:-1]:
            current = current.setdefault(part, {})  # type: ignore[assignment]
        current[parts[-1]] = None
    return tree


def render_tree(tree: dict[str, object], prefix: str = "") -> str:
    entries: list[str] = []
    for name, child in tree.items():
        display_name = html.escape(name)
        path = f"{prefix}{name}"
        if isinstance(child, dict):
            entries.append(
                f'<li class="directory"><span>{display_name}/</span>{render_tree(child, f"{path}/")}</li>'
            )
        else:
            href = quote(path, safe="/")
            entries.append(f'<li><a href="/files/{href}"><code>{display_name}</code></a></li>')
    return f"<ul>{''.join(entries)}</ul>"


def repository_page(paths: set[str]) -> bytes:
    tree = render_tree(build_tree(paths))
    return f"""<!doctype html>
<html lang=\"en\">
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Reddit Strategy Lab · repository map</title>
<style>
  :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background: #0b1019; color: #eaf0fa; }}
  body {{ max-width: 980px; margin: 0 auto; padding: 48px 28px 80px; }}
  .kicker {{ color: #9ee1ba; font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
  h1 {{ margin: 9px 0 8px; font-size: clamp(34px, 5vw, 55px); letter-spacing: -.055em; }}
  p {{ color: #aab9ca; line-height: 1.55; max-width: 720px; }}
  .stats {{ margin: 26px 0 36px; padding: 16px 19px; border: 1px solid #2c3b50; border-radius: 11px; background: #121c2a; color: #bbcadc; font-size: 14px; }}
  .stats strong {{ color: #fff; }}
  ul {{ list-style: none; margin: 0; padding-left: 22px; }}
  body > ul {{ padding-left: 0; }}
  li {{ margin: 6px 0; color: #8fa2b9; }}
  .directory > span {{ color: #aee4c5; font-weight: 750; }}
  a {{ color: #aad5ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; text-underline-offset: 3px; }}
  code {{ font-size: 13px; }}
  .tip {{ font-size: 13px; }}
</style>
<main>
  <div class=\"kicker\">Local repository browser</div>
  <h1>Reddit Strategy Lab</h1>
  <p>Every item below is tracked by Git and can be opened directly. Ignored market data, local post imports, credentials, run logs and <code>.git</code> are deliberately unavailable here.</p>
  <div class=\"stats\"><strong>{len(paths)} tracked files</strong> · current checked-out repository · click any file to inspect it</div>
  {tree}
  <p class=\"tip\">The main entry points are <a href=\"/files/README.md\">README.md</a>, <a href=\"/files/docs/case-studies.md\">docs/case-studies.md</a>, and <a href=\"/files/examples/reports/2020-2024/index.html\">the 2020–2024 visual report</a>.</p>
</main>
</html>""".encode()


class RepositoryHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required stdlib method name
        path = urlsplit(self.path).path
        paths = tracked_paths(REPOSITORY_ROOT)
        if path in {"/", "/tree"}:
            body = repository_page(paths)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/files/"):
            relative = unquote(path.removeprefix("/files/"))
            candidate = (REPOSITORY_ROOT / relative).resolve()
            if relative in paths and candidate.is_file() and REPOSITORY_ROOT in candidate.parents:
                content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                payload = candidate.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

        self.send_error(HTTPStatus.NOT_FOUND, "Tracked file not found")

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8772)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), RepositoryHandler) as server:
        print(f"Repository map: http://127.0.0.1:{args.port}/")
        server.serve_forever()


if __name__ == "__main__":
    main()
