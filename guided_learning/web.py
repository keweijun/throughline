"""Command-line entry for the local learning interface."""
import argparse

from .providers import ProviderSettings
from .server import serve


def main():
    parser = argparse.ArgumentParser(description='Local guided learning interface')
    parser.add_argument('--workspace', required=True, help='Course workspace directory')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--provider', help='Provider ID from your provider settings for this run')
    parser.add_argument('--model', help='Model name for this run')
    parser.add_argument('--effort', choices=('minimal', 'low', 'medium', 'high'), help='Reasoning effort for this run')
    parser.add_argument('--config', help='Provider settings file (default: per-user config directory)')
    args = parser.parse_args()
    override = {k: v for k, v in (('provider', args.provider), ('model', args.model), ('effort', args.effort)) if v}
    settings = ProviderSettings(args.config, override=override)
    settings.active()  # fail fast on an unknown --provider
    serve(args.workspace, port=args.port, settings=settings,
          on_ready=lambda port: print(f'Learning interface: http://127.0.0.1:{port}', flush=True))


if __name__ == '__main__':
    main()
