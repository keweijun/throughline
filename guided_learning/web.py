"""Command-line entry for the local learning interface."""
import argparse
import json
import os

from . import library
from .commands import host_record
from .server.settings import TeacherSettings
from .server import serve


def _record(port):
    path = host_record()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'pid': os.getpid(), 'port': port}), encoding='utf-8')


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
    parser.add_argument('--effort', choices=('minimal', 'low', 'medium', 'high'), help='Reasoning effort for this run')
    parser.add_argument('--config', help='Teacher settings file (default: per-user config directory)')
    parser.add_argument('--record', action='store_true', help='Record this host for `guided-learning open` and `stop`')
    args = parser.parse_args()
    settings = TeacherSettings(args.config, override={'model': args.model, 'effort': args.effort})

    def ready(port):
        if args.record:
            _record(port)
        print(f'Learning interface: http://127.0.0.1:{port}', flush=True)
    try:
        serve(args.workspace, port=args.port, settings=settings, on_ready=ready,
              library_root=args.library or library.default_root())
    finally:
        if args.record:
            _forget()


if __name__ == '__main__':
    main()
