"""Open exercises in two sections of the first chapter, with the learner in its second section."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Chapter exercises'})
execute(root,{'op':'curriculum.outline','chapters':[{'id':'one','title':'Chapter one'},{'id':'two','title':'Chapter two'}]})
execute(root,{'op':'curriculum.chapter.save','chapter_id':'one','concepts':[{'id':'a','title':'First section'},{'id':'b','title':'Second section'}]})
execute(root,{'op':'curriculum.chapter.save','chapter_id':'two','concepts':[{'id':'c','title':'Third section'}]})
def exercises(cid,questions):
 job={'id':'questions-'+cid,'concept_id':cid,'action':'generate'}
 execute(root,{'op':'mainline.enter','concept_id':cid,'goal':cid,'next_step':'practice','request_id':cid})
 execute(root,{'op':'practice.job','job':job})
 execute(root,{'op':'stream.start','id':job['id'],'concept_id':cid,'prompt':'Exercise service','channel':'practice','record_user':False})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps({'questions':[{'question':q,'origin':'self_created','source_refs':[]} for q in questions]})})
 execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
 execute(root,{'op':'practice.complete','id':job['id']})
exercises('a',['First section exercise'])
exercises('b',['Second section exercise'])
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  emit({'kind':'final','text':'A lesson.'});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
