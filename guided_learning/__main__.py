import argparse
import json
import sys
import traceback
from pathlib import Path
from . import background, commands, library
from .api import execute
from .store import OperationError


def saved_teacher_models():
    """The learner's saved Teacher settings, which name the model in a background handoff."""
    from .server.settings import TeacherSettings  # imported only when a handoff needs it
    try:
        return TeacherSettings().current()
    except OperationError:
        return {}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in commands.COMMANDS:
        return commands.main(argv)
    background.teacher_models = saved_teacher_models
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
    except Exception as exc:  # a bug, not a bad request; still answer in the JSON shape Codex parses
        traceback.print_exc()
        response, code = {'ok': False, 'error': {'code': 'internal_error', 'message': f'{exc.__class__.__name__}: {exc}'}}, 1
    print(json.dumps(response, ensure_ascii=True))
    return code


def throughline(argv=None):
    """The `throughline` command: `guided-learning`, except that on its own it opens the app as the launcher does."""
    argv = sys.argv[1:] if argv is None else argv
    return main(argv or ['open'])


if __name__ == '__main__':
    sys.exit(main())
