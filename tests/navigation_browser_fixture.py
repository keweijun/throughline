from pathlib import Path
import tempfile, threading
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
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
  text='## Unit overview\n\nUnderstand interference through superposition of two paths.\n\nAdd **probability amplitudes**, then take the squared magnitude:\n\n$$\nP=|a+b|^2\n$$\n\n| Path | Amplitude |\n| --- | --- |\n| First | $a$ |\n\n[Source '+s['id']+' / line-2]\n\nEarlier records cite like this: [来源 '+s['id']+' / line-2]\n\n<img src=x onerror="window.pwned=true"><script>window.pwned=true</script>\n\n'+('\n\nThis is a complete lesson paragraph, preserving the reading position.'*60)
  emit({'kind':'delta','text':text});emit({'kind':'final','text':text});emit({'kind':'complete'})
try:serve(root,port=0,runner=Runner(),settings=TeacherSettings(Path(root)/'settings.json'),on_ready=lambda port:print(port,flush=True))
finally:scratch.cleanup()
