from pathlib import Path
import tempfile, threading
from guided_learning.api import execute
from guided_learning.providers import ProviderSettings
from guided_learning.server import serve
scratch=tempfile.TemporaryDirectory()
root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Quantum Guided Learning · Navigation acceptance'})
p=root/'source.md';p.write_text('# Probability\nNormalization condition',encoding='utf-8')
s=execute(root,{'op':'source.register','path':str(p)})['source'];ref={'source_id':s['id'],'revision':s['revision'],'unit_id':'line-2'}
execute(root,{'op':'curriculum.save','concepts':[{'id':'wave','title':'Wave superposition','links':[ref]},{'id':'state','title':'Quantum states and measurement','prerequisites':['wave']}],'route':['wave','state'],'coverage':[]})
execute(root,{'op':'position.save','request_id':'setup','position':{'concept_id':'wave','goal':'Understand amplitudes through wave superposition','progress':'We have seen how a crest and a trough cancel.','next_step':'Explain interference through superposition of two paths.'}})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  chinese='Use the selected teaching language: Simplified Chinese' in prompt
  text='## 单元导览\n\n中文讲解：先合成概率幅。' if chinese else '## Unit overview\n\nEnglish lesson: combine amplitudes first.'
  emit({'kind':'delta','text':text})
  if cancel.wait(2): return
  text+='\n\n讲解完成。' if chinese else '\n\nLesson complete.'
  emit({'kind':'final','text':text});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=ProviderSettings(Path(root)/'providers.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
