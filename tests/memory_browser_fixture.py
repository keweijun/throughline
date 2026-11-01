from pathlib import Path
import tempfile
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory()
root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Quantum · Course memory'})
execute(root,{'op':'curriculum.save','concepts':[{'id':'wave','title':'Wave superposition'}],'route':['wave'],'coverage':[]})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  if 'Practice only' in prompt:
   text='{"questions":[{"question":"Add two amplitudes.","origin":"self_created","source_refs":[]}]}'
  elif 'is telling their teacher how they like to be taught' in prompt:
   text='{"reply":"I will keep my answers short.","remember":["Keep answers short"],"forget":[]}'
  else:
   text=('A plane wave $e^{ikx}$ has one wavelength.\n<course-memory>{"entries":[{"kind":"taught_term","text":"plane wave"},'
         '{"kind":"difficulty","text":"Adding probabilities instead of amplitudes"},{"kind":"preference","text":"One step at a time"}],"cleared":[]}</course-memory>')
  emit({'kind':'delta','text':text});emit({'kind':'final','text':text});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
