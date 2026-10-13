"""Public CLI seam shared by behavioral scenarios; every call is a fresh process."""
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def call_cli(case, workspace, op, error=None, **fields):
    if op in ('position.save', 'mainline.enter'):
        fields.setdefault('request_id', str(uuid.uuid4()))
    process = subprocess.run([sys.executable, '-m', 'guided_learning', '--workspace', str(workspace)], input=json.dumps({'op':op, **fields}), text=True, encoding='utf-8', capture_output=True, cwd=ROOT)
    case.assertTrue(process.stdout.strip(), process.stderr)
    response = json.loads(process.stdout)
    if error:
        case.assertFalse(response['ok'], response)
        case.assertEqual(response['error']['code'], error, response)
        case.assertNotEqual(process.returncode, 0)
        return response
    case.assertEqual(process.returncode, 0, process.stdout + process.stderr)
    case.assertTrue(response['ok'], response)
    return response['result']
