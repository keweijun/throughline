"""A section with three exercises the teacher wrote, one of them attempted; the teacher writes different ones on request."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Different exercises'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Original section'},{'id':'b','title':'Next section'}],'route':['a','b'],'coverage':[]})
execute(root,{'op':'mainline.enter','concept_id':'a','goal':'Original goal','next_step':'practice','request_id':'a'})
def complete(job,result):
 execute(root,{'op':'practice.job','job':job})
 execute(root,{'op':'stream.start','id':job['id'],'concept_id':'a','prompt':'Exercise service','channel':'practice','record_user':False})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps(result)})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
 execute(root,{'op':'practice.complete','id':job['id']})
complete({'id':'questions','concept_id':'a','action':'generate'},{'questions':[{'question':q,'origin':'self_created','source_refs':[]} for q in ('First exercise','Second exercise','Attempted exercise')]})
complete({'id':'assess','concept_id':'a','action':'assess','task_id':'questions:2','answer':'An attempt'},{'feedback':'Not yet.','outcome':'needs_work'})
def question(text):
 return json.dumps({'questions':[{'question':text,'origin':'self_created','source_refs':[]}]})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  if 'another exercise like this one' in prompt: text=question('Another one like the first')
  # The learner's note reaches the teacher, which writes to it.
  elif 'asked for different exercises' in prompt: text=question('Fresh exercise with little arithmetic' if 'Less arithmetic' in prompt else 'Fresh exercise')
  else: text='New section explanation'
  emit({'kind':'final','text':text});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
