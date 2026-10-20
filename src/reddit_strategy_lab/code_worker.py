"""Trusted bootstrap, passed as source to an OS-isolated Python interpreter.

Never import generated code in the host. The wire response is always untrusted.
"""

BOOTSTRAP = r"""
import json, sys, resource
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
wire = sys.stdout
sys.stdout = sys.stderr

def emit(value):
    wire.write(json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n')
    wire.flush()

try:
    initial = json.loads(sys.stdin.readline(262145))
    namespace = {'__name__': 'generated_strategy'}
    exec(compile(initial['source'], '<strategy>', 'exec'), namespace)
    strategy = namespace['Strategy'](initial['parameters'])
    emit({'ready': True})
    for line in sys.stdin:
        message = json.loads(line)
        commands = strategy.on_event(message['event'], message['portfolio'])
        emit({'sequence': message['event']['sequence'], 'commands': commands})
except BaseException as exc:
    # No source values, stack, paths, or market outcomes in diagnostics.
    emit({'error': type(exc).__name__})
    sys.exit(1)
"""
