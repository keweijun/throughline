"""Four exercises in the original section, including successful and incomplete attempts."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Practice continuity'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Original section'},{'id':'b','title':'Next section'}],'route':['a','b'],'coverage':[]})
execute(root,{'op':'mainline.enter','concept_id':'a','goal':'Original goal','next_step':'practice','request_id':'a'})
def complete(job,result):
 execute(root,{'op':'practice.job','job':job})
 execute(root,{'op':'stream.start','id':job['id'],'concept_id':'a','prompt':'Exercise service','channel':'practice','record_user':False})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps(result)})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
 execute(root,{'op':'practice.complete','id':job['id']})
complete({'id':'questions','concept_id':'a','action':'generate'},{'questions':[{'question':q,'origin':'self_created','source_refs':[]} for q in ('First exercise','Second exercise','Needs work exercise','Passed exercise')]})
for index,outcome in ((2,'needs_work'),(3,'passed')):
 complete({'id':'assess'+str(index),'concept_id':'a','action':'assess','task_id':'questions:'+str(index),'answer':'An attempt'},{'feedback':'Teacher feedback','outcome':outcome})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  emit({'kind':'final','text':'New section explanation'});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
