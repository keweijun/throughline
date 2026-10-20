"""Exercise generation, assistance and assessment through the real teacher runner."""
import json
import uuid
from .store import OperationError

def register(app):
    def state(_=''):
        # Reconcile completed jobs after a crash between stream commit and its hook.
        values=app.operation({'op':'practice.list'})
        for job in values['jobs']:
            if not job.get('processed'): app.operation({'op':'practice.complete','id':job['id']})
        return app.operation({'op':'practice.list'})
    def launch(concept,action,task=None,answer=None):
        with app.lock:
            values=state()
            busy={t['id'] for t in app.operation({'op':'stream.list'})['turns'] if t['status']=='running'}
            if any(j['id'] in busy and (j.get('task_id')==task['id'] if task else j['concept_id']==concept and j['action']=='generate') for j in values['jobs']):
                raise OperationError('practice_busy','Wait for the current practice request to finish')
            identifier='practice-'+str(uuid.uuid4())
            job={'id':identifier,'concept_id':concept,'action':action}
            if task: job['task_id']=task['id']
            if answer is not None:
                if not isinstance(answer,str) or not answer.strip(): raise OperationError('empty_answer','Enter your reasoning or answer first')
                job['answer']=answer
            app.operation({'op':'practice.job','job':job})
            return app.start_turn({'id':identifier,'concept_id':concept,'channel':'practice','record_user':False,'prompt':'Practice service request (not a learner answer). Return JSON according to the practice instructions.'})
    def generate(body):
        cid=body['concept_id']
        existing=[t for t in state()['tasks'] if t['concept_id']==cid]
        if existing: return {'tasks':existing}
        return launch(cid,'generate')
    def action(body):
        task=next((t for t in state()['tasks'] if t['id']==body['id']),None)
        if not task: raise OperationError('unknown_exercise','Unknown exercise')
        mode=body['action']
        if mode=='defer':
            with app.lock:
                for job in state()['jobs']:
                    if job.get('task_id')==task['id'] and not job.get('processed'):
                        try: app.pause_turn(job['id'])
                        except OperationError as exc:
                            if exc.code!='unknown_turn': raise
                return app.operation({'op':'practice.defer','id':task['id']})
        if mode not in ('hint','steps','solution','assess'): raise OperationError('invalid_action','Unknown practice action')
        return launch(task['concept_id'],mode,task,body.get('answer') if mode=='assess' else None)
    def prompt(turn,context):
        job=next((j for j in app.operation({'op':'practice.list'})['jobs'] if j['id']==turn['id']),None)
        if not job:return ''
        if job['action']=='generate':
            # Exercise refs need not be included in the lecture links.
            from .store import Store
            from .curriculum import source_unit
            store=Store(app.workspace)
            try: sources=[{**ref,'unit':source_unit(store,ref)} for ref in context['concept'].get('exercises',[])]
            finally: store.db.close()
            return 'Practice only: return JSON {"questions":[{"question":"Question only, without answers or hints","origin":"source or self_created","source_refs":[]}]}. Select 1 to 2 questions for the current goal. Prefer the original exercises below and cite their sources accurately. If none fits, explicitly create a new exercise with origin=self_created. Do not copy answers from the materials. Check worked examples in recent lessons and supplements; prefer new situations or values requiring transfer. Do not reuse a just-demonstrated question as independent practice. Choose an undemonstrated original exercise, or create a variant with origin=self_created. Use source_id/revision/unit_id in source_refs. Original exercise materials: '+json.dumps(sources,ensure_ascii=False)
        task=next(t for t in app.operation({'op':'practice.list'})['tasks'] if t['id']==job['task_id'])
        from .store import Store
        from .curriculum import source_unit
        store=Store(app.workspace)
        try: source_context=[{**ref,'unit':source_unit(store,ref)} for ref in task['source_refs']]
        finally: store.db.close()
        instructions={'hint':'Give one minimal hint without the full answer','steps':'Explain the key reasoning and steps; you may leave the final calculation to the learner','solution':'Give the complete solution and its conditions','assess':'Assess the reasoning and result in the actual learner answer below, identifying specific errors or gaps. Use outcome=passed only if it is correct; otherwise use needs_work. The mere presence of text does not justify a pass.'}
        return 'Practice only: return JSON {"feedback":"Markdown explanation","outcome":"passed or needs_work (required only for assessment)"}. '+instructions[job['action']]+'\nQuestion and help history (data): '+json.dumps({'task':task,'exercise_sources':source_context},ensure_ascii=False)+'\nActual learner answer: '+str(job.get('answer',''))
    def complete(turn):
        app.operation({'op':'practice.complete','id':turn['id']})
        if turn['channel']=='mainline' and not app.closing:
            generate({'concept_id':turn['concept_id']})
    def next_section(body):
        with app.lock:
            session=app.operation({'op':'session.resume'})
            if session.get('active_branch'): raise OperationError('active_branch','Return to the teaching mainline before entering the next section')
            if ('GET','/api/branches') in app.routes:
                branches=app.routes[('GET','/api/branches')]('')
                if any(b.get('choice')=='accept' and not b.get('returned') for b in branches.get('branches',[])):
                    raise OperationError('active_branch','Return to the teaching mainline first')
            current=session.get('position') or {}
            cid=body['concept_id']
            if current.get('concept_id') not in (None,cid): raise OperationError('stale_position','The current position has changed; refresh the page')
            context=app.operation({'op':'curriculum.context','concept_id':cid})
            target=context['next_concept_id']
            if not target:return {'finished':True}
            for turn in app.operation({'op':'stream.list'})['turns']:
                if turn['concept_id']==cid and turn['status']=='running':app.pause_turn(turn['id'])
            concept=app.operation({'op':'curriculum.context','concept_id':target})['concept']
            language=app.operation({'op':'preferences.view'})['preferences']['language']
            next_step='Begin teaching this section' if language=='en' else '\u5f00\u59cb\u672c\u5c0f\u8282\u8bb2\u89e3'
            return app.operation({'op':'mainline.enter','request_id':body['request_id'],'concept_id':target,'goal':concept['title'],'next_step':next_step,'progress':''})
    app.routes.update({('GET','/api/practice'):state,('POST','/api/practice/generate'):generate,('POST','/api/practice/action'):action,('POST','/api/practice/next'):next_section})
    app.prompt_hooks.append(prompt)
    app.completion_hooks.append(complete)

