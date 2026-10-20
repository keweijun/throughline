"""Deterministic model boundary for testing the actual bilingual UI/HTTP flow."""
import json
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.web import create_server

scratch=tempfile.TemporaryDirectory()
root=Path(scratch.name)
execute(root,{'op':'course.init','title':'Bilingual course'})
source=root/'notes.md';source.write_text('# Source\nOriginal source text stays unchanged.',encoding='utf-8')
registered=execute(root,{'op':'source.register','path':str(source)})['source']
ref={'source_id':registered['id'],'revision':registered['revision'],'unit_id':'line-2'}
execute(root,{'op':'curriculum.save','concepts':[{'id':'a','title':'Amplitudes','links':[ref],'exercises':[ref]},{'id':'b','title':'Projection'}],'route':['a','b'],'coverage':[]})
execute(root,{'op':'mainline.enter','request_id':'setup','concept_id':'a','goal':'Understand amplitudes','next_step':'Read the lesson'})


class Runner:
    def __init__(self):self.calls=[]

    def run(self,prompt,cwd,emit,cancel):
        chinese='selected teaching language: Simplified Chinese' in prompt
        if 'Practice only: return JSON {"questions"' in prompt:
            channel='exercise'
            text=json.dumps({'questions':[{'question':'\u4e2d\u6587\u7ec3\u4e60\u9898' if chinese else 'English exercise remains unchanged.','origin':'source','source_refs':[ref]}]})
        elif 'Practice only: return JSON {"feedback"' in prompt:
            channel='feedback'
            text=json.dumps({'feedback':'\u4e2d\u6587\u7ec3\u4e60\u63d0\u793a' if chinese else 'English feedback','outcome':'needs_work'})
        elif 'Internal preparation task' in prompt:
            channel='preparation';text='\u4e2d\u6587\u5907\u8bfe' if chinese else 'English preparation'
        elif 'Branch decision protocol' in prompt:
            channel='branch'
            text=('\u4e2d\u6587\u65c1\u652f\u56de\u7b54' if chinese else 'English side answer')+'<teaching-decision>'+json.dumps({'depth':'short','category':'local','rationale':'Local clarification','suggest_supplement':False,'supplement_goal':''})+'</teaching-decision>'
        else:
            channel='lesson';text=('## \u5355\u5143\u5bfc\u89c8\n\n\u4e2d\u6587\u6559\u5b66\u5185\u5bb9' if chinese else '## Unit overview\n\nEnglish lesson remains unchanged.')+f'\n\n[Source {ref["source_id"]} / line-2]'
        self.calls.append({'language':'zh-CN' if chinese else 'en','channel':channel})
        emit({'kind':'delta','text':text});emit({'kind':'final','text':text});emit({'kind':'complete'})


runner=Runner()
server=create_server(root,port=0,runner=runner)
server.app.routes[('GET','/api/test/calls')]=lambda _:runner.calls
print(server.server_port,flush=True)
try:server.serve_forever()
finally:server.server_close();scratch.cleanup()
