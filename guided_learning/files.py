"""Files Codex links to in a Studio reply, opened as Codex's own app opens them.

A link to one of the open course's sources opens in the app's reader, at the linked line; any other file opens on
the learner's computer. Only documents open in their own app: anything that might run as a program instead (a script,
an installer, a web page) is shown in the file manager, as is a folder. A link to a file that is gone shows the
nearest folder that still exists, as Codex does.
"""
import os
from pathlib import Path

from . import commands
from .launcher import _popen
from .store import OperationError

# Files that open in a viewer or editor and run nothing on any platform's default app.
DOCUMENTS = {
    '.pdf', '.md', '.markdown', '.txt', '.text', '.json', '.yaml', '.yml', '.toml', '.csv', '.tsv', '.tex', '.bib',
    '.doc', '.docx', '.odt', '.rtf', '.ppt', '.pptx', '.odp', '.key', '.xls', '.xlsx', '.ods', '.epub',
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.svg', '.heic',
}


def resolve(raw, base):
    """The file a link names: absolute as written, or relative to the folder Codex worked in."""
    if not isinstance(raw, str) or not raw.strip():
        raise OperationError('invalid_request', 'path must name a file')
    path = Path(os.path.expanduser(raw.strip()))
    return (path if path.is_absolute() else Path(base) / path).resolve()


def source_location(sources, path, line=None):
    """Where a course source opens for a link to it, or to the document it was converted from; None for other files."""
    key = os.path.normcase(str(path))
    for source in sources:
        original = (source.get('converted_from') or {}).get('path')
        names = [source['path']] + ([original] if original else [])
        if not source.get('revision') or key not in (os.path.normcase(n) for n in names):
            continue
        pdf = source['path'].lower().endswith('.pdf')
        # A line only means a line of the text itself, not of the document a PDF was made from.
        unit = 'page-1' if pdf else f'line-{line}' if line and line > 0 and key == os.path.normcase(source['path']) else 'line-1'
        return {'source_id': source['id'], 'revision': source['revision'], 'unit_id': unit}
    return None


class Opener:
    """Opens a file or folder on this computer, in its own app or the file manager."""

    def __init__(self, platform=None, start=_popen):
        self.platform = platform or commands.platform()
        self.start = start  # runs a program without waiting for it

    def open(self, path):
        path = Path(path)
        target = path
        while not target.exists():
            if target.parent == target:
                raise OperationError('missing_file', f'{path} does not exist.')
            target = target.parent
        document = target.is_file() and target.suffix.lower() in DOCUMENTS
        try:
            self.start(self._command(target, document))
        except OSError as exc:
            raise OperationError('cannot_open', f'Could not open {target} ({exc}).') from exc
        return {'opened': str(target), 'shown': not document}

    def _command(self, path, document):
        reveal = path.is_file() and not document
        if self.platform == 'nt':
            return ['explorer', f'/select,{path}'] if reveal else ['explorer', str(path)]
        if self.platform == 'darwin':
            return ['open', '-R', str(path)] if reveal else ['open', str(path)]
        return ['xdg-open', str(path.parent if reveal else path)]  # no portable way to select the file itself
