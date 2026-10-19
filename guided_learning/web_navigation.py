"""Read-only course navigation and exact-revision source access."""
import hashlib
import importlib.util
import io
import threading
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode
from .store import OperationError


_PDF_LOCK=threading.Lock()


def render_pdf_page(data,page_number):
    if importlib.util.find_spec('pypdfium2') is None or importlib.util.find_spec('PIL') is None:
        raise OperationError('renderer_unavailable','原页图像未显示：请安装项目 pdf 扩展，或使用原 PDF 链接。')
    # PDFium forbids concurrent API calls, even for different documents.
    with _PDF_LOCK:
        import pypdfium2
        try:
            with pypdfium2.PdfDocument(data) as document:
                if not isinstance(page_number,int) or not 1<=page_number<=len(document):
                    raise OperationError('invalid_reference','Invalid PDF page')
                page=document[page_number-1]
                try:
                    width,height=page.get_size()
                    scale=min(2.0,1800/max(width,height))
                    bitmap=page.render(scale=scale)
                    try:
                        image=bitmap.to_pil()
                        try:
                            output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
                        finally: image.close()
                    finally: bitmap.close()
                finally: page.close()
        except OperationError: raise
        except Exception as exc:
            raise OperationError('render_failed','原页图像渲染失败；可通过原 PDF 链接核对。') from exc


def register(app):
    def preview(url):
        query=parse_qs(urlparse(url).query)
        request={'op':'curriculum.context'}
        if query.get('concept_id'): request['concept_id']=query['concept_id'][0]
        context=app.operation(request)
        route=app.operation({'op':'curriculum.view'})
        concept=context['concept']; index=route['route'].index(concept['id'])
        previous=next((c for c in route['concepts'] if index and c['id']==route['route'][index-1]),None)
        following=next((c for c in route['concepts'] if c['id']==context['next_concept_id']),None)
        overview=concept.get('overview',{})
        if not isinstance(overview,dict): overview={}
        target=concept.get('objective') or concept.get('goal') or '能够解释'+concept['title']+'，并应用到相关问题'
        context['overview']={
            'core_problem':overview.get('core_problem') or concept.get('core_question') or '如何理解'+concept['title']+'，它解决了什么问题？',
            'steps':overview.get('steps') or ['建立'+concept['title']+'的直观图像','明确关键关系、符号和适用条件','用例子检验理解，再尝试练习'],
            'prior':overview.get('prior') or ('建立在'+ '、'.join(c['title'] for c in context['prerequisites'])+'之上' if context['prerequisites'] else ('接续'+previous['title'] if previous else '从本课程的基础问题开始')),
            'next':overview.get('next') or ('为后续'+following['title']+'做准备' if following else '回顾本单元，将概念用于综合问题'),
            'target_ability':overview.get('target_ability') or target,
            'origin':'teacher' if overview else 'route_summary'}
        for source in context['sources']:
            mapping=next((m for m in route['coverage'] if all(m.get(k)==source[k] for k in ('source_id','revision','unit_id'))),{})
            source['verification']=mapping.get('verification','pending')
            source['url']='/api/navigation/source?'+urlencode({k:source[k] for k in ('source_id','revision','unit_id')})
        return context
    app.routes[('GET','/api/navigation/preview')]=preview
    def source_view(url):
        query=parse_qs(urlparse(url).query)
        ref={key:query.get(key,[''])[0] for key in ('source_id','revision','unit_id')}
        if not re.fullmatch(r'src-[0-9a-f]{24}',ref['source_id']) or not re.fullmatch(r'[0-9a-f]{64}',ref['revision']):
            raise OperationError('invalid_reference','Choose a registered source revision')
        snapshot=app.operation({'op':'source.read',**ref})
        unit=next((u for u in snapshot['units'] if u['id']==ref['unit_id']),None)
        if unit is None: raise OperationError('invalid_reference','Unknown source location')
        root=(app.workspace/'sources').resolve()
        path=(root/ref['source_id']/ref['revision']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise OperationError('unavailable_source','Source snapshot unavailable')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=ref['revision']:
            raise OperationError('unavailable_source','Source snapshot integrity check failed')
        kind=Path(snapshot['path']).suffix.lower()
        if query.get('image')==['1']:
            if kind!='.pdf': raise OperationError('invalid_reference','Only PDF pages have rendered previews')
            return render_pdf_page(data,unit.get('locator',{}).get('page')),'image/png'
        if query.get('raw')==['1']:
            if kind!='.pdf': raise OperationError('invalid_reference','Only registered PDF snapshots can be opened directly')
            return data,'application/pdf'
        route=app.operation({'op':'curriculum.view'})
        mapping=next((m for m in route['coverage'] if all(m.get(k)==v for k,v in ref.items())),{})
        current=next((s for s in app.operation({'op':'course.status'})['sources'] if s['id']==ref['source_id']),{})
        available=importlib.util.find_spec('pypdfium2') is not None and importlib.util.find_spec('PIL') is not None
        return {**ref,**unit,'image_url':('/api/navigation/source?'+urlencode({**ref,'image':'1'})) if kind=='.pdf' and unit.get('locator',{}).get('page') and available else None,
                'render_message':None if available else '原页图像未显示：需要安装项目 pdf 扩展。仍可打开原 PDF 核对。','title':Path(snapshot['path']).name,'kind':kind,'verification':mapping.get('verification','pending'),'stale':current.get('revision')!=ref['revision'],
                'pdf_url':('/api/navigation/source?'+urlencode({**ref,'raw':'1'})+'#page='+str(unit['locator']['page'])) if kind=='.pdf' and unit.get('locator',{}).get('page') else None}
    app.routes[('GET','/api/navigation/source')]=source_view
    def overview_prompt(turn,context):
        if turn['channel']!='mainline': return ''
        prior=[t for t in app.operation({'op':'stream.list'})['turns'] if t['id']!=turn['id'] and t['channel']=='mainline' and t['concept_id']==turn['concept_id'] and t['status']=='completed']
        if prior:
            return '本小节已有讲解。开头用一两句接续当前目标和未完成步骤，避免重复完整单元导览。'
        return '''这是本小节在学习界面的首次正式授课。请把有实质内容的「## 单元导览」放在正式回复最前面，然后直接开始本节讲解，无需学习者再确认。
导览用简短具体语言说明：核心问题（本单元究竟解释什么现象或解决什么矛盾）、主要步骤（约三步，每步必须有本主题的具体概念，不能只写“直观—公式—练习”）、与已学先修及后续内容的联系、目标能力（学完能解释或计算什么）。
利用给定课程路线、来源与实际主线目标组织；不把待核验资料写成已确认事实。不机械复述目录，不插入“正在准备”状态话术。导览与完整讲解在同一次回复中生成和保存，保留后续讲解所需的推导、条件与例子。'''
    app.prompt_hooks.append(overview_prompt)
