"""PDF pages drawn as images: for the reader, for Codex reading a source (ADR 0019), and as figure crops."""
import importlib.util
import io
import threading
from pathlib import Path
from .store import OperationError

_LOCK = threading.Lock()  # PDFium forbids concurrent API calls, even for different documents
SIZE = 1800  # pixels on the long side of a page as the reader shows it
MIN_SIZE, MAX_SIZE = 200, 4000
MAX_SCALE = 6.0  # a small crop is drawn sharper, but never beyond this many pixels per PDF point


def available():
    return importlib.util.find_spec('pypdfium2') is not None and importlib.util.find_spec('PIL') is not None


def valid_box(box):
    """A box on a page as [left, top, right, bottom], fractions of the page's width and height from its top left."""
    return (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in box)
            and box[0] < box[2] and box[1] < box[3])


def render(document, page_number, box=None, size=SIZE):
    """PNG bytes of a page of `document` (a PDF file's path, or its bytes), or of the `box` on it, drawn so its long side
    is about `size` pixels. A path lets PDFium read only what the page needs, so a large PDF never sits in memory."""
    if not available():
        raise OperationError('renderer_unavailable', 'Original page image unavailable: install the project pdf extra, or use the original PDF link.')
    with _LOCK:
        import pypdfium2
        try:
            with pypdfium2.PdfDocument(str(document) if isinstance(document, Path) else document) as document:
                if not isinstance(page_number, int) or not 1 <= page_number <= len(document):
                    raise OperationError('invalid_reference', 'Invalid PDF page')
                page = document[page_number - 1]
                try:
                    width, height = page.get_size()
                    left, top, right, bottom = box or (0, 0, 1, 1)
                    longest = max(width * (right - left), height * (bottom - top))
                    # Only the box is drawn: crop is what to cut off each edge, in PDF units, left, bottom, right, top.
                    crop = (left * width, (1 - bottom) * height, (1 - right) * width, top * height)
                    bitmap = page.render(scale=min(MAX_SCALE, size / longest), crop=crop)
                    try:
                        image = bitmap.to_pil()
                        try:
                            output = io.BytesIO()
                            image.save(output, format='PNG')
                            return output.getvalue()
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError('render_failed', 'Original page rendering failed; check the original PDF link.') from exc
