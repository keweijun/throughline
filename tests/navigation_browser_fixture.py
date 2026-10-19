from pathlib import Path
import tempfile, threading
from guided_learning.api import execute
from guided_learning.web import create_server
scratch=tempfile.TemporaryDirectory()
root=Path(scratch.name)
execute(root,{'op':'course.init','title':'量子导学 · 导航验收'})
p=root/'source.md';p.write_text('# 概率\n归一化条件',encoding='utf-8')
s=execute(root,{'op':'source.register','path':str(p)})['source'];ref={'source_id':s['id'],'revision':s['revision'],'unit_id':'line-2'}
execute(root,{'op':'curriculum.save','concepts':[{'id':'wave','title':'波的叠加','links':[ref]},{'id':'state','title':'量子态与测量','prerequisites':['wave']}],'route':['wave','state'],'coverage':[]})
execute(root,{'op':'position.save','request_id':'setup','position':{'concept_id':'wave','goal':'从波的叠加理解概率幅','progress':'已经理解波峰与波谷相遇会抵消。','next_step':'用两个路径的叠加解释干涉。'}})
class Runner:
 def run(self,prompt,cwd,emit,cancel):
  text='## 单元导览\n\n从两条路径的叠加理解干涉。\n\n**概率幅**相加，然后取模平方：\n\n$$P=|a+b|^2$$\n\n| 路径 | 幅 |\n| --- | --- |\n| 第一条 | $a$ |\n\n[来源 '+s['id']+' / line-2]\n\n<img src=x onerror="window.pwned=true"><script>window.pwned=true</script>\n\n'+('\n\n这是完整的讲解段落，保留阅读位置。'*60)
  emit({'kind':'delta','text':text});emit({'kind':'final','text':text});emit({'kind':'complete'})
server=create_server(root,port=0,runner=Runner());print(server.server_port,flush=True)
try:server.serve_forever()
finally:server.server_close();scratch.cleanup()
