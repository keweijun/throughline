"""Saved course after a host crash, with two selectable lectures and a partial supplement."""
from pathlib import Path
import tempfile
from guided_learning.api import execute
from guided_learning.web import create_server
scratch=tempfile.TemporaryDirectory();root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Recovery regression'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Older lesson'},{'id':'b','title':'Current lesson'}],'route':['a','b'],'coverage':[]})
for cid in ('a','b'):
 execute(root,{'op':'mainline.enter','concept_id':cid,'goal':cid,'next_step':'practice','request_id':cid})
 execute(root,{'op':'stream.start','id':cid,'concept_id':cid,'prompt':'Explain '+cid})
 execute(root,{'op':'stream.event','id':cid,'attempt':1,'sequence':1,'kind':'final','text':('Older selectable lecture explains amplitudes.' if cid=='a' else 'Current lecture explains measurement.')})
 execute(root,{'op':'stream.event','id':cid,'attempt':1,'sequence':2,'kind':'complete'})
execute(root,{'op':'branch.begin','id':'recovery','question':'Need foundations','main_turn_id':'b'})
execute(root,{'op':'stream.start','id':'branch:recovery','concept_id':'b','prompt':'Need foundations','channel':'sidequestion'})
execute(root,{'op':'stream.event','id':'branch:recovery','attempt':1,'sequence':1,'kind':'final','text':'Please accept a supplement.'})
execute(root,{'op':'stream.event','id':'branch:recovery','attempt':1,'sequence':2,'kind':'complete'})
execute(root,{'op':'branch.decide','id':'recovery','decision':{'depth':'short','category':'prerequisite','rationale':'Required foundation','suggest_supplement':True,'supplement_goal':'Amplitude'}})
execute(root,{'op':'branch.choose','id':'recovery','choice':'accept'})
execute(root,{'op':'stream.start','id':'supplement:recovery','concept_id':'b','prompt':'Explain amplitude','channel':'sidequestion','record_user':False})
execute(root,{'op':'stream.event','id':'supplement:recovery','attempt':1,'sequence':1,'kind':'delta','text':'Partial supplement before host crash.'})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  if '学习者已接受补讲' in prompt:
   emit({'kind':'delta','text':'Regenerated supplement is still running.'});cancel.wait(20);return
  emit({'kind':'final','text':'Answer about the selected passage.'});emit({'kind':'complete'})
server=create_server(root,port=0,runner=Runner());print(server.server_port,flush=True)
try:server.serve_forever()
finally:server.server_close();scratch.cleanup()
