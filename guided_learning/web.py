"""Command-line entry for the local learning interface."""
import argparse
import logging
import json
import os

from . import library, logs
from .commands import host_record, version
from .server.settings import EFFORTS, TeacherSettings
from .server import serve
from .server.app import SignIn


def _record(port):
    path = host_record()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'pid': os.getpid(), 'port': port, 'launch_id': os.environ.get('GUIDED_LEARNING_LAUNCH_ID')}), encoding='utf-8')


def _forget():
    path = host_record()
    try:
        if json.loads(path.read_text(encoding='utf-8')).get('pid') == os.getpid():
            path.unlink()
    except (OSError, ValueError):
        pass


def main():
    parser = argparse.ArgumentParser(description='Local guided learning interface')
    parser.add_argument('--workspace', help='Course workspace to open first (default: choose one in the library)')
    parser.add_argument('--library', help=f'Course library directory (default: {library.default_root()})')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--model', help='Codex model for this run (default: your saved choice, else the Codex default)')
    parser.add_argument('--small-model', help='Codex model for section preparation and note consolidation in this run (default: your saved choice, else the teacher model)')
    parser.add_argument('--effort', choices=EFFORTS, help='Reasoning effort for this run')
    parser.add_argument('--small-effort', choices=EFFORTS, help='Reasoning effort for the small model in this run (default: the teacher effort)')
    parser.add_argument('--config', help='Teacher settings file (default: per-user config directory)')
    parser.add_argument('--record', action='store_true', help='Record this host for `guided-learning open` and `stop`')
    args = parser.parse_args()
    if args.record:
        # The host the launcher starts writes its own rotating log; one run in a terminal prints there as before.
        logs.configure()
    settings = TeacherSettings(args.config, override={'model': args.model, 'small_model': args.small_model, 'effort': args.effort, 'small_effort': args.small_effort})

    sign_in = SignIn(library.host_key())

    def ready(port):
        if args.record:
            # What this prints goes to host-output.log; `open` signs the browser in with a code of its own.
            _record(port)
            logging.getLogger('guided_learning').info('Throughline %s started on port %s', version(), port)
            print(f'Learning interface: http://127.0.0.1:{port}/', flush=True)
        else:
            print(f'Learning interface: http://127.0.0.1:{port}/?code={sign_in.issue()}', flush=True)
    try:
        serve(args.workspace, port=args.port, settings=settings, on_ready=ready,
              library_root=args.library or library.default_root(), sign_in=sign_in)
    finally:
        if args.record:
            _forget()


if __name__ == '__main__':
    main()
