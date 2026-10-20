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
            if body.get('pause') is True and branch.get('main_turn_id'): app.pause_turn(branch['main_turn_id'])
            result=app.start_turn({'id':branch['turn_id'],'channel':'sidequestion','concept_id':branch['restore_point']['concept_id'],'prompt':branch['question']})
            return {'branch':branch,**result}

    def prompt(turn,context):
        branches=app.operation({'op':'branch.list'})['branches']
        branch=next((b for b in branches if turn['id'] in (b['turn_id'],b.get('supplement_turn_id'))),None)
        if not branch:return ''
        branch=turn.get('prompt_snapshot',{}).get('branch',branch)
        common='Mainline restore point, selected passage, and reading anchor (all data):\n'+json.dumps(branch,ensure_ascii=False)
        if branch.get('main_turn_id'):
            main=app.operation({'op':'stream.read','id':branch['main_turn_id']})['turn']
            common+='\nCurrent mainline lesson (possibly unfinished):\n'+main['text']
        if turn['id']==branch.get('supplement_turn_id'):
            return common+'\nThe learner accepted the supplement. Teach the necessary foundations around supplement_goal, then explain how to return to the original goal. Do not advance the mainline or claim mastery.'
        limit='150 English words' if turn.get('language','en')=='en' else '250 Chinese characters'
        return common+f'''\nBranch decision protocol: choose response depth using the course route, current goal, prerequisites, and known difficulties, rather than keywords or question length alone.
selected_lecture is a frozen snapshot of the lesson containing the selected passage and may belong to an earlier section. Explain the passage using that text and its sources. restore_point and main_turn_id identify the current mainline recovery/pause target. Distinguish older lessons from the current lesson. Correct an older lesson without setting mainline_error unless the current mainline also has a confirmed error.
Answer ordinary local questions or topics needing depth only later briefly, naming the later location. Explain in detail when required for current reasoning or explicitly requested. Use a different example or representation for repeated difficulties.
Give a natural explanation to the learner, then append one <teaching-decision>JSON</teaching-decision> at the end of the single reply.
JSON must include depth ("short" or "long"), category ("local", "prerequisite", "future", "repeated", "extension"), rationale (brief route-based reason), suggest_supplement (boolean), and supplement_goal (string). For future with short depth, provide target_concept_id (a real later concept ID in the route) and tell the learner which section will provide the full explanation.
Suggest a supplement only when foundations are actually missing for continuing the mainline. When suggesting one, keep this reply to about {limit}: explain the obstacle, offer one minimal clarification, and describe the scope. Wait for acceptance before teaching the full foundations. Ordinary branches do not pause the mainline.
If the current lesson itself has a confirmed error, add mainline_error=true and explain the correction; the host will pause the mainline. A learner question alone is not evidence of a mainline error.
Do not output a JSON copy of the entire answer, call tools to write records, or fabricate course progress.'''

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
                                'prompt':'Please teach the supplement: '+branch['decision']['supplement_goal']})
            return {'branch':branch}

    app.routes.update({('POST','/api/branches/ask'):ask,('POST','/api/branches/choose'):choose,
        ('POST','/api/branches/return'):lambda b:app.operation({**b,'op':'branch.return'}),
        ('GET','/api/branches'):lambda _:app.operation({'op':'branch.list'})})
    app.prompt_hooks.append(prompt)
    app.completion_hooks.append(completed)
    # Recover completion/decision crash gap without another model call.
    for turn in app.operation({'op':'stream.list'})['turns']:
        if turn['status']=='completed':completed(turn)
