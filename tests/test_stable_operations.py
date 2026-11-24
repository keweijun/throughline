"""The operations docs/stability.md promises through 1.x: named in the skill for Codex to call, or frozen chat-teaching
ones. Removing or renaming one is a 2.0 change from 1.0 (review.write and review.sets left before it, ADR 0025); a new one the skill names is added to STABLE here."""
import glob
import re
import unittest
from importlib import import_module
from pathlib import Path

from guided_learning import api

SKILL = Path(api.__file__).resolve().parent / 'skill'

STABLE = {
    'annotations.delete', 'annotations.list', 'annotations.save', 'course.init', 'course.profile.save', 'course.rename',
    'course.status', 'cover.list', 'cover.save',
    'curriculum.chapter.save', 'curriculum.chapter.view', 'curriculum.check', 'curriculum.context', 'curriculum.coverage',
    'curriculum.outline', 'curriculum.save', 'curriculum.view', 'drill.list', 'drill.write', 'key_points.revise', 'key_points.view', 'mainline.enter', 'mistakes.list', 'memory.confirm', 'memory.save',
    'position.save', 'practice.add', 'practice.list', 'practice.retire', 'practice.revise', 'preferences.save',
    'preferences.view', 'review.context', 'session.resume', 'sheet.list', 'sheet.save', 'source.figure', 'source.read',
    'source.readings.save', 'source.register', 'source.render', 'source.search', 'stream.summaries', 'widgets.list',
    'widgets.save',
}
# Named in the skill only to say they belong to the app.
APP_ONLY = {'practice.complete', 'practice.skip'}
FROZEN = {'interaction.record', 'sidequestion.open', 'sidequestion.answer', 'sidequestion.continue', 'deferred.create'}
# Dotted names in the skill that are fields, files or programs, not operations.
NOT_OPERATIONS = {'converted_from.revision', 'course.position.concept_id', 'position.concept_id', 'position.return_to',
                  'powershell.exe', 'readings.unread', 'store.db'}


def registered():
    operations = {}
    for name in api.MODULES:
        operations.update(import_module(f'guided_learning.{name}').OPERATIONS)
    return operations


class StableOperations(unittest.TestCase):
    def test_every_promised_operation_is_still_registered(self):
        missing = sorted((STABLE | FROZEN) - set(registered()))
        self.assertEqual(missing, [], 'docs/stability.md promises these through 1.x')

    def test_every_operation_the_skill_names_is_promised(self):
        text = ''.join(Path(p).read_text(encoding='utf-8') for p in [SKILL / 'SKILL.md', *glob.glob(str(SKILL / 'references' / '*.md'))])
        named = set(re.findall(r'"op": ?"([a-z_.]+)"', text)) | set(re.findall(r'`([a-z_]+(?:\.[a-z_]+)+)`', text))
        unknown = sorted(named - STABLE - APP_ONLY - NOT_OPERATIONS)
        self.assertEqual(unknown, [], 'a new operation the skill names joins STABLE (and the 1.x promise)')


if __name__ == '__main__':
    unittest.main()
