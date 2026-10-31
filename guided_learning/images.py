"""Attached images: pictures the learner adds to an answer, a side question or a learner note.

They are stored once in the course workspace under a name derived from their content, and records refer to them by
that name. The folder keeps its first name, from when only answers had images, so existing courses need no migration.
"""
import hashlib
import os
import re
from pathlib import Path
from .store import OperationError

FOLDER = 'answer_images'
TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
NAME = re.compile(r'[0-9a-f]{64}\.(png|jpg|gif|webp)')
MAX = 6


def kind(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
    if data.startswith(b'\xff\xd8\xff'): return 'jpg'
    if data[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'webp'
    return None


def save(workspace, data):
    """Store an image by content and return its name; the same image saved twice is one file."""
    suffix = kind(data)
    if not suffix: raise OperationError('unsupported_image', 'Attach a PNG, JPEG, GIF or WebP image')
    name = hashlib.sha256(data).hexdigest() + '.' + suffix
    folder = Path(workspace) / FOLDER
    folder.mkdir(exist_ok=True)
    if not (folder / name).is_file():
        partial = folder / (name + '.partial')
        partial.write_bytes(data)
        os.replace(partial, folder / name)
    return name


def path(workspace, name):
    found = Path(workspace) / FOLDER / name if isinstance(name, str) and NAME.fullmatch(name) else None
    if not found or not found.is_file(): raise OperationError('unknown_image', 'Unknown image')
    return found


def validate(workspace, request, key='images'):
    """The request's attached images, checked to be 1 to MAX distinct stored images; an empty list when it has none."""
    if key not in request: return []
    images = request[key]
    if not isinstance(images, list) or not 1 <= len(images) <= MAX or len(set(images)) != len(images):
        raise OperationError('invalid_request', f'{key} must list 1 to {MAX} distinct images')
    for name in images: path(workspace, name)
    return list(images)


def described(count, what):
    """A prompt line telling the teacher that `count` images come with `what` as image inputs."""
    if not count: return ''
    return (f'\nThe learner attached {count} image{"s" if count != 1 else ""} to {what} as image inputs, in order; '
            'read them as part of it, and say so if any is illegible.')
