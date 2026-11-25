"""A library host that requires its key (`library.host_key()`), as `throughline open` starts one; the key is 64 a characters."""
import tempfile
from pathlib import Path
from throughline.server import serve
from throughline.server.settings import TeacherSettings
scratch = tempfile.TemporaryDirectory()
serve(port=0, settings=TeacherSettings(Path(scratch.name) / 'settings.json'), library_root=Path(scratch.name) / 'library',
      key='a' * 64, on_ready=lambda port: print(port, flush=True))
