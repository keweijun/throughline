"""A two-part exercise the teacher assesses part by part, and an exercise assessed before exercises had parts (ADR 0011)."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.store import Store
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Exercise parts'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Rules'},{'id':'b','title':'Next section'}],'route':['a','b'],'coverage':[]})
execute(root,{'op':'mainline.enter','concept_id':'a','goal':'Use the rule','next_step':'practice','request_id':'a'})
def complete(job,result):
 execute(root,{'op':'practice.job','job':job})
 execute(root,{'op':'stream.start','id':job['id'],'concept_id':'a','prompt':'Exercise service','channel':'practice','record_user':False})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps(result)})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
 execute(root,{'op':'practice.complete','id':job['id']})
complete({'id':'questions','concept_id':'a','action':'generate'},{'questions':[
 {'question':'Two parts:\n1. State the rule.\n2. Apply it.','parts':['State the rule.','Apply it.'],'origin':'self_created','source_refs':[]},
 {'question':'An exercise from before parts','origin':'self_created','source_refs':[]}]})
# The old exercise's assessment has an outcome and no part statuses, as every assessment did before parts.
task=execute(root,{'op':'practice.list'})['tasks'][1]
complete({'id':'old','concept_id':'a','action':'assess','task_id':task['id'],'answer':'An old answer'},{'feedback':'Correct.','outcome':'passed'})
store=Store(root)
with store.db:
 stored=store.get('practice_tasks',task['id'])
 for entry in stored['history']: entry.pop('parts',None)
 store.put('practice_tasks',task['id'],stored)
store.db.close()
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  answer=prompt.rsplit('Actual learner answer:',1)[-1]
  parts=['correct' if 'rule is' in answer else 'not_attempted','correct' if 'applied' in answer else 'partly_correct' if 'apply' in answer else 'not_attempted']
  emit({'kind':'final','text':json.dumps({'feedback':'Checked part by part.','parts':parts})});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
