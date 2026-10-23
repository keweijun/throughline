import tempfile
import unittest
from guided_learning.api import execute

class PreparationState(unittest.TestCase):
    def test_preparation_is_internal_and_ready_does_not_change_learning(self):
        with tempfile.TemporaryDirectory() as path:
            def op(**kw): return execute(path,kw)
            op(op='course.init',title='Physics')
            op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            before=op(op='session.resume')
            job=op(op='preparation.enqueue',id='prep')['job']
            self.assertEqual(job['concept_id'],'b')
            op(op='stream.start',id='prep',concept_id='b',prompt='Internal prep',channel='preparation',record_user=False)
            op(op='stream.event',id='prep',attempt=1,sequence=1,kind='final',text='Prepared explanation with uncertainty')
            op(op='stream.event',id='prep',attempt=1,sequence=2,kind='complete')
            op(op='preparation.reconcile')
            ready=op(op='preparation.view',concept_id='b')['ready']
            self.assertEqual(ready['content'],'Prepared explanation with uncertainty')
            self.assertEqual(op(op='session.resume'),before)
            self.assertFalse(op(op='evidence.view',concept_id='b')['independently_verified'])

    def test_route_and_source_changes_discard_material(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as path:
            def op(**kw): return execute(path,kw)
            op(op='course.init',title='Physics')
            file=Path(path)/'notes.md';file.write_text('Old source',encoding='utf8')
            op(op='source.register',path=str(file))
            concepts=[{'id':c,'title':c} for c in 'abc']
            op(op='curriculum.save',concepts=concepts,route=['a','b','c'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            op(op='preparation.enqueue',id='p')
            op(op='stream.start',id='p',concept_id='b',prompt='Internal',channel='preparation',record_user=False)
            file.write_text('New source',encoding='utf8');op(op='source.register',path=str(file))
            op(op='stream.event',id='p',attempt=1,sequence=1,kind='final',text='Stale text')
            op(op='stream.event',id='p',attempt=1,sequence=2,kind='complete')
            state=op(op='preparation.view',concept_id='b')
            self.assertIsNone(state['ready']);self.assertEqual(state['jobs'][0]['status'],'stale')
            op(op='preparation.enqueue',id='p2')
            op(op='curriculum.save',concepts=concepts,route=['a','c','b'],coverage=[],confirm_reorder=True)
            self.assertEqual(op(op='preparation.view')['jobs'][1]['status'],'stale')

    def test_idle_pipeline_preempted_by_foreground_and_ready_is_injected(self):
        import threading
        import time
        from guided_learning.server import Host
        class Runner:
            entered=threading.Event();release=threading.Event();cancelled=threading.Event()
            prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                if 'Internal preparation task' in prompt:
                    self.entered.set()
                    while not self.release.wait(.01):
                        if cancel.is_set():self.cancelled.set();return
                    text='PREP_UNIQUE: explain with explicit uncertainty'
                else:text='Foreground answer'
                emit({'kind':'final','text':text});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            runner=Runner();app=Host(path,runner=runner)
            try:
                self.assertTrue(runner.entered.wait(3),'automatic next-section preparation must start')
                foreground=app.start_turn({'concept_id':'a','channel':'sidequestion','prompt':'Small question'})['turn']
                self.assertEqual(app.wait(foreground['id'],3)['status'],'completed')
                self.assertTrue(runner.cancelled.wait(3))
                runner.release.set()
                deadline=time.time()+4
                while time.time()<deadline:
                    state=app.preparation.state()
                    if any(j['status']=='ready' for j in state['jobs']):break
                    time.sleep(.05)
                self.assertTrue(any(j['status']=='ready' for j in state['jobs']))
                op(op='mainline.enter',request_id='next',concept_id='b',goal='B',next_step='explain')
                turn=app.start_turn({'concept_id':'b','channel':'sidequestion','prompt':'Explain'})['turn'];app.wait(turn['id'],3)
                self.assertIn('PREP_UNIQUE',runner.prompts[-1])
                self.assertNotIn('PREP_UNIQUE',str(op(op='session.resume')['recent_interactions']))
            finally:app.close()

    def test_failed_preparation_falls_back_and_shutdown_does_not_schedule(self):
        import time
        from guided_learning.server import Host
        class Runner:
            prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                if 'Internal preparation task' in prompt:raise RuntimeError('preparation provider unavailable')
                emit({'kind':'final','text':'Teacher fallback'});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            runner=Runner();app=Host(path,runner=runner)
            deadline=time.time()+3
            while time.time()<deadline:
                jobs=app.preparation.state()['jobs']
                if jobs and jobs[-1]['status']=='failed':break
                time.sleep(.03)
            self.assertEqual(jobs[-1]['status'],'failed')
            time.sleep(.5)
            self.assertEqual(len(app.preparation.state()['jobs']),1)
            op(op='mainline.enter',request_id='next',concept_id='b',goal='B',next_step='explain')
            turn=app.start_turn({'concept_id':'b','channel':'sidequestion','prompt':'Explain'})['turn'];self.assertEqual(app.wait(turn['id'],3)['final_text'],'Teacher fallback')
            self.assertIn('Complete the necessary source checks',runner.prompts[-1]);app.close()
            count=len(runner.prompts);time.sleep(.5)
            self.assertEqual(len(runner.prompts),count)
            self.assertFalse(app.preparation.schedule()['scheduled'])

    def test_orphaned_preparation_recovers_as_failed(self):
        from guided_learning.server import Host
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            op(op='preparation.enqueue',id='crashed-before-launch')
            app=Host(path)
            try:self.assertEqual(app.preparation.state()['jobs'][0]['status'],'failed')
            finally:app.close()


def review_course(path):
    """Course whose second section links a Markdown line and a PDF page; the first links another line."""
    import json
    from pathlib import Path
    from sample_pdf import write_pdf
    def op(**kw):return execute(path,kw)
    op(op='course.init',title='Physics')
    notes=Path(path)/'notes.md';notes.write_text('E = mc^2\nUnrelated line',encoding='utf8')
    slides=Path(path)/'slides.pdf';write_pdf(slides,[['Momentum p = mv']])
    md=op(op='source.register',path=str(notes))['source'];pdf=op(op='source.register',path=str(slides))['source']
    line1={'source_id':md['id'],'revision':md['revision'],'unit_id':'line-1'}
    line2={**line1,'unit_id':'line-2'}
    page={'source_id':pdf['id'],'revision':pdf['revision'],'unit_id':'page-1'}
    op(op='curriculum.save',concepts=[{'id':'a','title':'A','links':[line2]},{'id':'b','title':'B','links':[line1,page]}],route=['a','b'],coverage=[])
    review=lambda *refs:'Prepared material\n<source-review>'+json.dumps({'reviews':[{**r,'verification':'verified','verification_note':'Matches the original'} for r in refs]})+'</source-review>'
    return op,line1,line2,page,review


class SourceReview(unittest.TestCase):
    def test_preparation_records_only_its_own_targets_and_pdf_pages_need_an_image(self):
        with tempfile.TemporaryDirectory() as path:
            op,line1,line2,page,review=review_course(path)
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            job=op(op='preparation.enqueue',id='p')['job']
            self.assertEqual([(t['unit_id'],t['kind']) for t in job['review']],[('line-1','markdown'),('page-1','pdf')])
            op(op='stream.start',id='p',concept_id='b',prompt='Internal',channel='preparation',record_user=False)
            op(op='stream.event',id='p',attempt=1,sequence=1,kind='final',text=review(line1,page,line2))
            op(op='stream.event',id='p',attempt=1,sequence=2,kind='complete')
            ready=op(op='preparation.view',concept_id='b')['ready']
            self.assertEqual(ready['content'],'Prepared material')
            self.assertEqual((ready['review_result']['verified'],ready['review_result']['ignored']),([line1],2))
            units={u['unit_id']:u['verification'] for u in op(op='curriculum.coverage')['units']}
            self.assertEqual(units,{'line-1':'verified','line-2':'pending','page-1':'pending'})
            self.assertEqual(op(op='preparation.view',concept_id='b')['ready']['id'],'p','own reviews must not make material stale')

    def test_host_attaches_pdf_pages_and_prepares_the_first_section_without_a_position(self):
        import time
        from guided_learning.server import Host
        with tempfile.TemporaryDirectory() as path:
            op,line1,line2,page,review=review_course(path)
            op(op='curriculum.save',concepts=[{'id':'a','title':'A','links':[line1,page]},{'id':'b','title':'B','links':[line2]}],route=['a','b'],coverage=[])
            class Runner:
                calls=[]
                def run(self,prompt,cwd,emit,cancel,images=()):
                    self.calls.append((prompt,list(images)))
                    emit({'kind':'final','text':review(line1,page)});emit({'kind':'complete'})
            runner=Runner();app=Host(path,runner=runner)
            try:
                deadline=time.time()+4
                while time.time()<deadline and not app.preparation.state('a')['ready']:time.sleep(.05)
                prompt,images=runner.calls[0]
                self.assertIn('attached image 1',prompt)
                self.assertEqual(len(images),1);self.assertTrue(images[0].startswith('data:image/png;base64,'))
                units={u['unit_id']:u for u in op(op='curriculum.coverage')['units']}
                self.assertEqual((units['page-1']['verification'],units['page-1']['verification_note']),('verified','Matches the original'))
                self.assertEqual(units['line-1']['verification'],'verified')
                turn=app.start_lesson({})['turn'];app.wait(turn['id'],3)
                sources={s['unit_id']:s['verification'] for s in op(op='stream.read',id=turn['id'])['turn']['prompt_snapshot']['context']['sources']}
                self.assertEqual(sources,{'line-1':'verified','page-1':'verified'})
                self.assertIn('Prepared material',runner.calls[-1][0])
            finally:app.close()
