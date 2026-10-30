"""One exercise, and a teacher that reports the images it was sent with an answer or a question."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Handwritten answers'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Integrals'}],'route':['a'],'coverage':[]})
execute(root,{'op':'mainline.enter','concept_id':'a','goal':'Integrate','next_step':'practice','request_id':'a'})
job={'id':'questions','concept_id':'a','action':'generate'}
execute(root,{'op':'practice.job','job':job})
execute(root,{'op':'stream.start','id':job['id'],'concept_id':'a','prompt':'Exercise service','channel':'practice','record_user':False})
execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps({'questions':[{'question':'Integrate x by hand.','origin':'self_created','source_refs':[]}]})})
execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
execute(root,{'op':'practice.complete','id':job['id']})
class Runner:
 def run(self,prompt,cwd,emit,cancel,images=()):
  seen=[Path(p) for p in images if Path(p).is_file() and Path(p).parent==root/'answer_images']
  report=f'I read {len(seen)} images in the course workspace.'
  emit({'kind':'final','text':json.dumps({'feedback':report,'outcome':'passed'}) if 'Practice only' in prompt else report});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
