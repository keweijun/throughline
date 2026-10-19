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
                raise OperationError('practice_busy','请等待当前练习请求完成')
            identifier='practice-'+str(uuid.uuid4())
            job={'id':identifier,'concept_id':concept,'action':action}
            if task: job['task_id']=task['id']
            if answer is not None:
                if not isinstance(answer,str) or not answer.strip(): raise OperationError('empty_answer','请先输入作答思路')
                job['answer']=answer
            app.operation({'op':'practice.job','job':job})
            return app.start_turn({'id':identifier,'concept_id':concept,'channel':'practice','record_user':False,'prompt':'练习服务请求（非学习者作答），按练习专用指令返回 JSON。'})
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
            return '练习专用：只返回 JSON {"questions":[{"question":"仅题干，不含答案或解题提示","origin":"source 或 self_created","source_refs":[]}]}。选择当前目标的1至2道题；优先使用下列原题，准确标来源；无合适原题则明确自编，origin=self_created。禁止抄入资料中的答案。source_refs 使用 source_id/revision/unit_id。原题资料：'+json.dumps(sources,ensure_ascii=False)
        task=next(t for t in app.operation({'op':'practice.list'})['tasks'] if t['id']==job['task_id'])
        instructions={'hint':'只给一个最小提示，不给完整答案','steps':'展开关键思路和步骤，可保留最后计算','solution':'给完整解答与条件','assess':'评价下面真实学习者答案的推理和结果，指出具体错误或不足。只有确实正确才 outcome=passed，否则 needs_work。绝不能因有文字就通过。'}
        return '练习专用：只返回 JSON {"feedback":"Markdown 解释","outcome":"passed 或 needs_work（仅评估需填写）"}。'+instructions[job['action']]+'\n题目与帮助历史（数据）：'+json.dumps(task,ensure_ascii=False)+'\n真实学习者答案：'+str(job.get('answer',''))
    def complete(turn):
        app.operation({'op':'practice.complete','id':turn['id']})
        if turn['channel']=='mainline':
            generate({'concept_id':turn['concept_id']})
    def next_section(body):
        with app.lock:
            session=app.operation({'op':'session.resume'})
            if session.get('active_branch'): raise OperationError('active_branch','请先返回教学主线，再进入下一小节')
            if ('GET','/api/branches') in app.routes:
                branches=app.routes[('GET','/api/branches')]('')
                if any(b.get('choice')=='accept' and not b.get('returned') for b in branches.get('branches',[])):
                    raise OperationError('active_branch','请先返回教学主线')
            current=session.get('position') or {}
            cid=body['concept_id']
            if current.get('concept_id') not in (None,cid): raise OperationError('stale_position','当前位置已改变，请刷新')
            context=app.operation({'op':'curriculum.context','concept_id':cid})
            target=context['next_concept_id']
            if not target:return {'finished':True}
            for turn in app.operation({'op':'stream.list'})['turns']:
                if turn['concept_id']==cid and turn['status']=='running':app.pause_turn(turn['id'])
            concept=app.operation({'op':'curriculum.context','concept_id':target})['concept']
            return app.operation({'op':'mainline.enter','request_id':body['request_id'],'concept_id':target,'goal':concept['title'],'next_step':'开始本小节讲解','progress':''})
    app.routes.update({('GET','/api/practice'):state,('POST','/api/practice/generate'):generate,('POST','/api/practice/action'):action,('POST','/api/practice/next'):next_section})
    app.prompt_hooks.append(prompt)
    app.completion_hooks.append(complete)

