import argparse
import json
import sys
from pathlib import Path
from .api import execute
from .store import OperationError

def main():
    parser = argparse.ArgumentParser(description='Execute one JSON course operation')
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--request', help='UTF-8 JSON request file; defaults to stdin')
    args = parser.parse_args()
    try:
        raw = Path(args.request).read_text(encoding='utf-8-sig') if args.request else sys.stdin.read()
        result = execute(args.workspace, json.loads(raw))
        response, code = {'ok': True, 'result': result}, 0
    except (OperationError, json.JSONDecodeError, OSError) as exc:
        response, code = {'ok': False, 'error': {'code': getattr(exc, 'code', 'invalid_request'), 'message': str(exc)}}, 1
    print(json.dumps(response, ensure_ascii=True))
    return code

if __name__ == '__main__':
    sys.exit(main())
