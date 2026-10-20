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
        raise OperationError('renderer_unavailable','Original page image unavailable: install the project pdf extra, or use the original PDF link.')
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
            raise OperationError('render_failed','Original page rendering failed; check the original PDF link.') from exc


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
        target=concept.get('objective') or concept.get('goal') or 'Explain '+concept['title']+' and apply it to related problems'
        context['overview']={
            'core_problem':overview.get('core_problem') or concept.get('core_question') or 'How can we understand '+concept['title']+' and what problem does it solve?',
            'steps':overview.get('steps') or ['Develop an intuitive picture of '+concept['title'],'Identify key relationships, notation, and conditions','Check understanding with an example, then try exercises'],
            'prior':overview.get('prior') or ('Builds on '+ ', '.join(c['title'] for c in context['prerequisites']) if context['prerequisites'] else ('Continues from '+previous['title'] if previous else 'Start with the fundamental questions of this course')),
            'next':overview.get('next') or ('Prepares for '+following['title'] if following else 'Review this unit and apply the concepts to combined problems'),
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
                'render_message':None if available else 'Original page image unavailable: install the project pdf extra. You can still open the original PDF.','title':Path(snapshot['path']).name,'kind':kind,'verification':mapping.get('verification','pending'),'stale':current.get('revision')!=ref['revision'],
                'pdf_url':('/api/navigation/source?'+urlencode({**ref,'raw':'1'})+'#page='+str(unit['locator']['page'])) if kind=='.pdf' and unit.get('locator',{}).get('page') else None}
    app.routes[('GET','/api/navigation/source')]=source_view
    def overview_prompt(turn,context):
        if turn['channel']!='mainline': return ''
        prior=[t for t in app.operation({'op':'stream.list'})['turns'] if t['id']!=turn['id'] and t['channel']=='mainline' and t['concept_id']==turn['concept_id'] and t['status']=='completed']
        if prior:
            return 'This section already has a lesson. Open with one or two sentences resuming the current goal and unfinished steps, without repeating the full unit overview.'
        heading='Unit overview' if turn.get('language','en')=='en' else '\u5355\u5143\u5bfc\u89c8'
        return f'''This is the first formal lesson for this section in the learning interface. Begin the reply with a substantive "## {heading}", then teach the section directly without asking the learner to confirm.
Use brief, concrete language to describe the core problem (the phenomenon or contradiction this unit explains), main steps (about three, each naming specific concepts rather than just intuition, formulas, and practice), connections to learned prerequisites and later topics, and target ability (what the learner can explain or calculate afterward).
Organize the lesson using the supplied route, sources, and actual mainline goal. Keep unverified material explicitly uncertain. Avoid mechanically repeating the contents or inserting preparation status messages. Generate and save the overview and full explanation in the same reply, retaining the necessary derivations, conditions, and examples.'''
    app.prompt_hooks.append(overview_prompt)
