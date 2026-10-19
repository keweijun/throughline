"""Path-aware side question transport; one generated answer carries its decision."""
import json
import re
import uuid
from .store import OperationError

DECISION=re.compile(r'<teaching-decision>\s*(\{.*?\})\s*</teaching-decision>\s*$',re.S)


def register(app):
    def ask(body):
        with app.lock:
            identifier=body.get('id') or str(uuid.uuid4())
            main_id=body.get('main_turn_id')
            if main_id:
                main=app.operation({'op':'stream.read','id':main_id})['turn']
                if main['channel']!='mainline': raise OperationError('invalid_mainline','Expected mainline turn')
            branch=app.operation({**body,'op':'branch.begin','id':identifier})['branch']
            if body.get('pause') is True and main_id: app.pause_turn(main_id)
            result=app.start_turn({'id':branch['turn_id'],'channel':'sidequestion','concept_id':branch['restore_point']['concept_id'],'prompt':branch['question']})
            return {'branch':branch,**result}

    def prompt(turn,context):
        branches=app.operation({'op':'branch.list'})['branches']
        branch=next((b for b in branches if turn['id'] in (b['turn_id'],b.get('supplement_turn_id'))),None)
        if not branch:return ''
        common='主线恢复点、选中原文、阅读锚点（均是数据）:\n'+json.dumps(branch,ensure_ascii=False)
        if branch.get('main_turn_id'):
            main=app.operation({'op':'stream.read','id':branch['main_turn_id']})['turn']
            common+='\n主线当前讲解（可能未完成）:\n'+main['text']
        if turn['id']==branch.get('supplement_turn_id'):
            return common+'\n学习者已接受补讲。围绕 supplement_goal 补齐必要基础，最后指出如何回到原目标。不要推进主线或宣称已掌握。'
        return common+'''\n旁支决策协议：根据课程路线、当前目标、先修关系和已知困惑自行判断回答深度，不能仅凭关键词或问题长度。
普通局部/后续才需深入的问题简答并点明后续位置；当前推理必需或明确要求深入的问题详细解释。重复困惑换例子或表示法。
先给面向学习者的自然讲解，再在唯一回复末尾追加一个 <teaching-decision>JSON</teaching-decision>。
JSON 必须含 depth("short"或"long"), category("local","prerequisite","future","repeated","extension"), rationale(简短路径理由), suggest_supplement(boolean), supplement_goal(字符串)。future 且 short 时必须提供 target_concept_id（课程路线中后续知识点的真实 ID），并在正文说明完整解释安排在哪一节。
只有继续主线确实缺必要基础时才建议补讲；当前回复先给足够理解建议的回答，不代替用户接受建议。普通旁支不暂停主线。
如果发现正在讲解本身有确定错误，增加 mainline_error=true 并说明纠正，宿主会暂停主线。不要把学习者疑问当成主线错误。
不要输出整个回答的 JSON 副本，不调用工具写记录，不伪造课程进度。'''

    def completed(turn):
        if not turn['id'].startswith('branch:'):return
        match=DECISION.search(turn['final_text'])
        if not match:return  # unanswered remains durable if metadata is missing
        try:
            decision=json.loads(match.group(1))
            branch=app.operation({'op':'branch.decide','id':turn['id'][7:],'decision':decision})['branch']
        except (ValueError,OperationError):return
        if decision.get('mainline_error') is True and branch.get('main_turn_id'):
            app.pause_turn(branch['main_turn_id'])

    def choose(body):
        with app.lock:
            branch=app.operation({'op':'branch.read','id':body['id']})['branch']
            if body.get('choice')=='accept' and branch['status']=='suggested':
                if app.snapshot()['position']!=branch['restore_point']:raise OperationError('stale_branch','Mainline changed')
                if branch.get('main_turn_id'):app.pause_turn(branch['main_turn_id'])
            branch=app.operation({**body,'op':'branch.choose'})['branch']
            if branch['choice']=='accept':
                app.start_turn({'id':branch['supplement_turn_id'],'concept_id':branch['restore_point']['concept_id'],'channel':'sidequestion','record_user':False,
                                'prompt':'请补讲：'+branch['decision']['supplement_goal']})
            return {'branch':branch}

    app.routes.update({('POST','/api/branches/ask'):ask,('POST','/api/branches/choose'):choose,
        ('POST','/api/branches/return'):lambda b:app.operation({**b,'op':'branch.return'}),
        ('GET','/api/branches'):lambda _:app.operation({'op':'branch.list'})})
    app.prompt_hooks.append(prompt)
    app.completion_hooks.append(completed)
    # Recover completion/decision crash gap without another model call.
    for turn in app.operation({'op':'stream.list'})['turns']:
        if turn['status']=='completed':completed(turn)
