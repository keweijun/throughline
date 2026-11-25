"""Serves a library build.py made, with the real Codex teacher and studio.py as Studio: python docs/screenshots/host.py <out> <port>."""
import sys
from pathlib import Path

from throughline.checks import CodexStatus
from throughline.files import Opener
from throughline.launcher import Launcher
from throughline.server import serve
from throughline.server.settings import TeacherSettings

out, port = Path(sys.argv[1]).resolve(), int(sys.argv[2])
serve(port=port, settings=TeacherSettings(out / 'config' / 'settings.json'), library_root=out / 'library',
      studio_command=[sys.executable, str(Path(__file__).with_name('studio.py')), str(out / 'studio.log')],
      launcher=Launcher(out / 'no-launcher' / 'throughline.desktop', platform='linux'),
      checks=CodexStatus(cheap=lambda: [], probe=lambda: None),
      opener=Opener(platform='linux', start=lambda command: None), on_ready=lambda p: print(p, flush=True))
