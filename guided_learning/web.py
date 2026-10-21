"""Command-line entry for the local learning interface."""
import argparse

from .server.settings import TeacherSettings
from .server import serve


def main():
    parser = argparse.ArgumentParser(description='Local guided learning interface')
    parser.add_argument('--workspace', required=True, help='Course workspace directory')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--model', help='Codex model for this run (default: your saved choice, else the Codex default)')
    parser.add_argument('--effort', choices=('minimal', 'low', 'medium', 'high'), help='Reasoning effort for this run')
    parser.add_argument('--config', help='Teacher settings file (default: per-user config directory)')
    args = parser.parse_args()
    settings = TeacherSettings(args.config, override={'model': args.model, 'effort': args.effort})
    serve(args.workspace, port=args.port, settings=settings,
          on_ready=lambda port: print(f'Learning interface: http://127.0.0.1:{port}', flush=True))


if __name__ == '__main__':
    main()
