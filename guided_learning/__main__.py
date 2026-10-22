import argparse
import json
import sys
from pathlib import Path
from . import commands, library
from .api import execute
from .store import OperationError

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in commands.COMMANDS:
        return commands.main(argv)
    parser = argparse.ArgumentParser(prog='guided-learning', description='Execute one JSON course operation, or run setup, open, stop or courses')
    parser.add_argument('--version', action='version', version=commands.version())
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--workspace', help='Course workspace directory')
    target.add_argument('--course', help='Course name in the per-user library')
    parser.add_argument('--request', help='UTF-8 JSON request file; defaults to stdin')
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace or library.course_path(library.default_root(), args.course)
        raw = Path(args.request).read_text(encoding='utf-8-sig') if args.request else sys.stdin.read()
        result = execute(workspace, json.loads(raw))
        response, code = {'ok': True, 'result': result}, 0
    except (OperationError, json.JSONDecodeError, OSError) as exc:
        response, code = {'ok': False, 'error': {'code': getattr(exc, 'code', 'invalid_request'), 'message': str(exc)}}, 1
    print(json.dumps(response, ensure_ascii=True))
    return code

if __name__ == '__main__':
    sys.exit(main())
