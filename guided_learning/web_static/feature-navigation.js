import {t,bind} from './i18n.js';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n};
const ui=(tag,key,values={},cls)=>bind(el(tag,null,cls),key,values);
export async function setup(app){
  const nav=app.elements.navigation, overview=app.elements.overview;
  const preview=el('section',null,'preview-view'),sourceView=el('section',null,'source-view');
  app.registerView('preview',preview);app.registerView('sources',sourceView);
  let contextKey='',requestVersion=0;
  const location=data=>data.locator?.page?t('Page {page}',{page:data.locator.page}):data.locator?.line?t('Line {line}',{line:data.locator.line}):t('Exact location missing');
  async function openSource(ref){
    const data=await app.api('/api/navigation/source?'+new URLSearchParams({source_id:ref.source_id,revision:ref.revision,unit_id:ref.unit_id}));
    sourceView.replaceChildren(el('h2',data.title),ui('p','{verification}{stale}',()=>({verification:t(data.verification==='verified'?'Verified':'Pending verification · check the original page'),stale:data.stale?t(' · historical revision'):''}),'source-status'));
    sourceView.append(ui('p','Revision {revision} · {location}',()=>({revision:data.revision.slice(0,12),location:location(data)})));
    if(data.pdf_url){
      const link=ui('a','Open original in a new window');link.href=data.pdf_url;link.target='_blank';link.rel='noopener';sourceView.append(link);
      if(data.image_url){
        const status=ui('p','Rendering original page…',{},'muted'),image=el('img');image.className='source-page';
        bind(image,'{title}, original page {page}',{title:data.title,page:data.locator.page},'alt');
        image.onload=()=>bind(status,'Original page image · Page {page}',{page:data.locator.page});
        image.onerror=()=>{image.hidden=true;bind(status,'Original page image unavailable: rendering failed or the pdf extra is missing. Use the original PDF link above.')};
        image.src=data.image_url;sourceView.append(status,image);
      }else sourceView.append(ui('p',data.render_message||'Original page image unavailable: no valid page number.',{},'source-status'));
    }else sourceView.append(data.text?el('pre',data.text):ui('pre','No text extracted at this location'));
    app.showView('sources');
  }
  app.openSource=openSource;
  function sources(container,data){
    const box=el('div',null,'source-links');box.append(ui('h3','Sources and verification'));
    if(!data.sources.length)box.append(ui('p','No locatable source is linked yet. Formulas and citations in the lesson still need verification.',{},'muted'));
    for(const ref of data.sources){
      const b=ui('button','{location} · {verification}',()=>({location:ref.locator?.page?t('Original page {page}',{page:ref.locator.page}):ref.locator?.line?t('Original line {line}',{line:ref.locator.line}):t('Location unavailable'),verification:t(ref.verification==='verified'?'Verified':'Pending verification')}),'secondary');
      b.onclick=()=>openSource(ref).catch(app.showError);box.append(b);
    }container.append(box);
  }
  function overviewContent(container,data,previewOnly=false){
    const o=data.overview;
    container.append(ui('small',previewOnly?'Preview only · learning position unchanged':o.origin==='teacher'?'Unit overview':'Route summary'),el('h2',data.concept.title));
    if(o.origin==='teacher'){
      container.append(el('p',o.core_problem,'core-question'));
      const steps=el('ol');for(const step of o.steps)steps.append(el('li',String(step)));container.append(steps);
      container.append(ui('p','{prior}; {next}',{prior:o.prior,next:o.next},'muted'),ui('p','Afterward you can: {ability}',{ability:o.target_ability}));
    }else{
      container.append(ui('p','Route summary; the first lesson will begin with a specific unit overview.',{},'muted'));
      const next=app.state?.curriculum.concepts.find(c=>c.id===data.next_concept_id);
      container.append(ui('p','Prerequisites: {prerequisites}',()=>({prerequisites:data.prerequisites.length?data.prerequisites.map(x=>x.title).join(', '):t('No prerequisites specified')})),
        ui('p','Up next: {next}',()=>({next:next?.title||t('Final section of this course route')})));
    }
    sources(container,data);
  }
  async function showPreview(id){const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(id));preview.replaceChildren();overviewContent(preview,data,true);app.showView('preview');if(matchMedia('(max-width:850px)').matches){nav.hidden=true;document.querySelector('#toggle-nav').setAttribute('aria-expanded','false')}}
  async function update(state){
    const current=state.position?.concept_id||state.curriculum.route[0];
    const hasLesson=state.turns.some(t=>t.channel==='mainline'&&t.concept_id===current&&['completed','running'].includes(t.status));
    const key=JSON.stringify([state.course.id,state.position,state.curriculum,state.sources,hasLesson]);
    if(key===contextKey)return;contextKey=key;const version=++requestVersion;
    nav.replaceChildren(ui('small','Learning route'),ui('h2','Course contents'),ui('p','Click a concept to preview',{},'muted'));
    for(const [i,id] of state.curriculum.route.entries()){
      const c=state.curriculum.concepts.find(c=>c.id===id), b=el('button',String(i+1).padStart(2,'0')+'  '+c.title,'route-item');
      if(id===current){b.classList.add('current');b.setAttribute('aria-current','step')}
      b.onclick=()=>showPreview(id).catch(app.showError);nav.append(b);
    }
    if(!current){overview.replaceChildren(ui('p','No learning route has been planned for this course.'));return}
    const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(current));if(version!==requestVersion)return;
    overview.replaceChildren();
    const summary=el('div',null,'position-bar');
    const ability=state.position?.goal||data.concept.objective||data.concept.goal||data.concept.overview?.target_ability;
    summary.append(ui('small','Current goal'),ability?el('strong',ability):ui('strong','Explain {title} and apply it to related problems',{title:data.concept.title}),ui('span','Next step: {step}',()=>({step:state.position?.next_step||t('Read the lesson, then try the exercises')}),'muted'));
    overview.append(summary);
    if(state.position?.progress){const progress=el('details'), title=ui('summary','Where you left off');progress.append(title,el('p',state.position.progress));overview.append(progress)}
    const details=el('details',null,'unit-overview'), keySeen='overview:'+state.course.id+':'+current;
    details.open=!hasLesson&&!localStorage.getItem(keySeen);
    details.append(ui('summary','{title} · {overview}',()=>({title:data.concept.title,overview:t(data.overview.origin==='teacher'?'Unit overview':'route and sources')})));
    const content=el('div');overviewContent(content,data);details.append(content);details.addEventListener('toggle',()=>{if(!details.open)localStorage.setItem(keySeen,'seen')});overview.append(details);
    if(state.session.recent_interactions.length){const unanswered=state.session.unanswered_questions.length;overview.prepend(ui('p','Continue learning “{title}”{unanswered}. Your reading position and unfinished lessons are retained.',()=>({title:data.concept.title,unanswered:unanswered?t(' · {count} questions awaiting answers',{count:unanswered}):''}),'resume-note'))}
  }
  // Exact references from the saved interaction win over a later curriculum revision.
  app.events.addEventListener('rendered',async e=>{
    const {node,turn}=e.detail;if(!turn||!/(?:\[Source\s|\[\u6765\u6e90\s)/.test(node.textContent))return;
    let refs=[];try{if(turn.status==='completed')refs=(await app.operation({op:'interaction.read',id:'stream:'+turn.id})).interaction.source_refs;else refs=(await app.operation({op:'curriculum.context',concept_id:turn.concept_id})).sources}catch{return}
    if(!node.isConnected)return;
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),texts=[];while(walker.nextNode())if(!walker.currentNode.parentElement.closest('code,pre,button,.katex'))texts.push(walker.currentNode);
    for(const text of texts){const regex=/\[(?:Source|\u6765\u6e90)\s+([^\s/]+)\s*\/\s*([^\]\s]+)\]/g;let match,last=0;const fragment=document.createDocumentFragment();while((match=regex.exec(text.textContent))){fragment.append(document.createTextNode(text.textContent.slice(last,match.index)));const ref=refs.find(r=>r.source_id===match[1]&&r.unit_id===match[2]);if(ref){const b=ui('button','View source',{},'citation');b.onclick=()=>openSource(ref).catch(app.showError);fragment.append(b)}else{fragment.append(document.createTextNode(match[0]),ui('span',' (location pending verification)'))}last=regex.lastIndex}if(last){fragment.append(document.createTextNode(text.textContent.slice(last)));text.replaceWith(fragment)}}
  });
  app.events.addEventListener('state',e=>update(e.detail).catch(app.showError));
}
