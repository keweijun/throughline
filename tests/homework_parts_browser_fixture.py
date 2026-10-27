"""Exercises from a homework question split across sections, and one from an unsplit question (ADR 0012)."""
import json,tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Homework parts'})
file=root/'homework.md';file.write_text('PS02-Q4 (1) Normalize. (2) Measure. (3) Evolve.\nPS02-Q5 Measure again.',encoding='utf-8')
source=execute(root,{'op':'source.register','path':str(file)})['source']
ref=lambda unit:{'source_id':source['id'],'revision':source['revision'],'unit_id':unit}
part={**ref('line-1'),'question':'PS02-Q4 (2)','required_concepts':['state','measure'],'part_of':'PS02-Q4',
      'other_parts':[{'question':'PS02-Q4 (1)','concept_id':'state'},{'question':'PS02-Q4 (3)'}]}
first={**ref('line-1'),'question':'PS02-Q4 (1)','required_concepts':['state'],'part_of':'PS02-Q4',
       'other_parts':[{'question':'PS02-Q4 (2)','concept_id':'measure'},{'question':'PS02-Q4 (3)'}]}
execute(root,{'op':'curriculum.save','concepts':[{'id':'state','title':'States','exercises':[first]},
              {'id':'measure','title':'Measurement','exercises':[part,{**ref('line-2'),'question':'PS02-Q5','required_concepts':['measure']}]}],
              'route':['state','measure'],'coverage':[]})
execute(root,{'op':'mainline.enter','concept_id':'measure','goal':'Measure','next_step':'practice','request_id':'measure'})
job={'id':'questions','concept_id':'measure','action':'generate'}
execute(root,{'op':'practice.job','job':job})
execute(root,{'op':'stream.start','id':job['id'],'concept_id':'measure','prompt':'Exercise service','channel':'practice','record_user':False})
execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':1,'kind':'final','text':json.dumps({'questions':[
 {'question':'Measure the state.','origin':'source','source_refs':[ref('line-1')],'exercise':'PS02-Q4 (2)'},
 {'question':'Measure again.','origin':'source','source_refs':[ref('line-2')],'exercise':'PS02-Q5'}]})})
execute(root,{'op':'stream.event','id':job['id'],'attempt':1,'sequence':2,'kind':'complete'})
execute(root,{'op':'practice.complete','id':job['id']})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  emit({'kind':'final','text':'Lesson.'});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
