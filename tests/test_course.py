from support import call_cli
import tempfile
import unittest
from pathlib import Path


class CourseCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.course = self.base / 'course'

    def call(self, op, error=None, workspace=None, **fields):
        return call_cli(self, workspace or self.course, op, error=error, **fields)

    def test_course_reopens_in_new_process_with_saved_position_and_isolation(self):
        created = self.call('course.init', title='Quantum')
        self.call('position.save', position={'goal': 'Understand wavefunctions', 'next_step': 'Explain normalization'})
        restored = self.call('course.status')
        self.assertEqual(restored['course']['id'], created['course']['id'])
        self.assertEqual(restored['position']['next_step'], 'Explain normalization')
        other = self.call('course.init', workspace=self.base / 'other', title='Calculus')
        self.assertNotEqual(created['course']['id'], other['course']['id'])
        self.assertIsNone(other['position'])
        self.assertEqual(self.call('course.init', title='Ignored')['course']['title'], 'Quantum')


    def test_source_registration_preserves_identity_revisions_and_line_locations(self):
        self.call('course.init', title='Quantum')
        source = self.base / 'wave.md'
        source.write_text('# Wavefunction\nNormalize the state.\n', encoding='utf-8')
        first = self.call('source.register', path=str(source))
        again = self.call('source.register', path=str(source))
        self.assertEqual(first['source']['id'], again['source']['id'])
        self.assertEqual(first['source']['revision'], again['source']['revision'])
        read = self.call('source.read', source_id=first['source']['id'])
        self.assertEqual(read['units'][1]['locator'], {'line': 2})
        self.assertEqual(read['units'][1]['text'], 'Normalize the state.')
        self.assertEqual(read['verification'], 'pending')
        source.write_text('# Wavefunction\nA changed explanation.\n', encoding='utf-8')
        changed = self.call('source.register', path=str(source))
        self.assertEqual(first['source']['id'], changed['source']['id'])
        self.assertNotEqual(first['source']['revision'], changed['source']['revision'])
        old = self.call('source.read', source_id=first['source']['id'], revision=first['source']['revision'])
        self.assertEqual(old['units'][1]['text'], 'Normalize the state.')
        self.assertEqual(len(self.call('course.status')['sources']), 1)


    def test_missing_and_corrupt_sources_are_visible_without_losing_previous_revision(self):
        self.call('course.init', title='Quantum')
        path = self.base / 'missing.md'
        failed = self.call('source.register', path=str(path))['source']
        self.assertEqual(failed['status'], 'failed')
        self.assertTrue(failed['errors'])
        path.write_text('Readable', encoding='utf-8')
        good = self.call('source.register', path=str(path))['source']
        path.unlink()
        failed_again = self.call('source.register', path=str(path))['source']
        self.assertEqual(failed_again['revision'], good['revision'])
        self.assertEqual(failed_again['status'], 'failed')
        self.assertEqual(self.call('source.read', source_id=good['id'])['units'][0]['text'], 'Readable')
        pdf = self.base / 'corrupt.pdf'
        pdf.write_bytes(b'not a pdf')
        bad_pdf = self.call('source.register', path=str(pdf))['source']
        self.assertEqual(bad_pdf['status'], 'failed')
        self.assertTrue(bad_pdf['errors'])
    def test_pdf_pages_keep_real_page_locations_and_empty_pdf_needs_review(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest('Install the pdf extra for PDF parser integration test')
        self.call('course.init', title='Quantum')
        pdf = self.base / 'slides.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.add_blank_page(width=300, height=200)
        writer.write(pdf)
        source = self.call('source.register', path=str(pdf))['source']
        self.assertEqual(source['status'], 'needs_review')
        result = self.call('source.read', source_id=source['id'])
        self.assertEqual([u['locator'] for u in result['units']], [{'page': 1}, {'page': 2}])
        self.assertEqual(result['verification'], 'pending')
        empty = self.base / 'empty.pdf'
        PdfWriter().write(empty)
        self.assertEqual(self.call('source.register', path=str(empty))['source']['status'], 'needs_review')


class LearnerProfile(unittest.TestCase):
    def test_profile_is_validated_saved_and_reaches_the_teacher(self):
        from guided_learning.api import execute
        from guided_learning.server.prompts import instructions
        with tempfile.TemporaryDirectory() as tmp:
            call_cli(self, tmp, 'course.init', title='Quantum')
            call_cli(self, tmp, 'course.profile.save', error='invalid_profile', profile={'goal': 'Exam', 'depth': 'deep'})
            call_cli(self, tmp, 'course.profile.save', error='invalid_profile', profile={'goal': 'Exam', 'depth': 'standard', 'prerequisites': [{'topic': 'Calculus', 'level': 'expert'}]})
            profile = {'goal': 'Pass the final', 'depth': 'rigorous', 'focus': 'Exam problems',
                       'prerequisites': [{'topic': 'Fourier transforms', 'level': 'none'},
                                         {'topic': 'Eigenvalues', 'level': 'some', 'check': 'Found eigenvalues of a 2x2 matrix; unsure about diagonalizing'}]}
            blank = {**profile, 'notes': ' ', 'prerequisites': [{**p, 'check': ''} if p['level'] == 'none' else p for p in profile['prerequisites']]}
            self.assertEqual(call_cli(self, tmp, 'course.profile.save', profile=blank)['profile'], profile)
            self.assertEqual(call_cli(self, tmp, 'course.status')['profile'], profile)
            execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'States'}], 'route': ['a'], 'coverage': []})
            turn = execute(tmp, {'op': 'stream.start', 'id': 'l1', 'channel': 'mainline', 'concept_id': 'a', 'prompt': 'Teach'})['turn']
            prompt = instructions(turn)  # the profile is stable course data
            self.assertIn('Fourier transforms', prompt)
            self.assertIn('unsure about diagonalizing', prompt)
            self.assertIn('learner_profile', prompt)
