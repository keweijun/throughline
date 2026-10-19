const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n};
export async function setup(app){
  const nav=app.elements.navigation, overview=app.elements.overview;
  const preview=el('section',null,'preview-view'),sourceView=el('section',null,'source-view');
  app.registerView('preview',preview);app.registerView('sources',sourceView);
  let contextKey='',requestVersion=0;
  async function openSource(ref){
    const data=await app.api('/api/navigation/source?'+new URLSearchParams({source_id:ref.source_id,revision:ref.revision,unit_id:ref.unit_id}));
    sourceView.replaceChildren(el('h2',data.title),el('p',(data.verification==='verified'?'Verified':'Pending verification · check the original page')+(data.stale?' · historical revision':''),'source-status'));
    sourceView.append(el('p','Revision '+data.revision.slice(0,12)+' · '+(data.locator?.page?'Page '+data.locator.page+'':data.locator?.line?'Line '+data.locator.line+'':'Exact location missing')));
    if(data.pdf_url){const link=el('a','Open original in a new window');link.href=data.pdf_url;link.target='_blank';link.rel='noopener';sourceView.append(link);if(data.image_url){const status=el('p','Rendering original page…','muted'),image=el('img');image.className='source-page';image.alt=data.title+' Page '+data.locator.page+' original page';image.onload=()=>{status.textContent='Original page image · Page '+data.locator.page+''};image.onerror=()=>{image.hidden=true;status.textContent='Original page image unavailable: rendering failed or the pdf extra is missing. Use the original PDF link above.'};image.src=data.image_url;sourceView.append(status,image)}else sourceView.append(el('p',data.render_message||'Original page image unavailable: no valid page number.','source-status'))}
    else {const text=el('pre',data.text||'No text extracted at this location');sourceView.append(text)}
    app.showView('sources');
  }
  app.openSource=openSource;
  function sources(container,data){
    const box=el('div',null,'source-links');box.append(el('h3','Sources and verification'));
    if(!data.sources.length)box.append(el('p','No locatable source is linked yet. Formulas and citations in the lesson still need verification.','muted'));
    for(const ref of data.sources){const b=el('button',(ref.locator?.page?'Original page '+ref.locator.page:ref.locator?.line?'Original line '+ref.locator.line+'':'Location unavailable')+' · '+(ref.verification==='verified'?'Verified':'Pending verification'),'secondary');b.onclick=()=>openSource(ref).catch(app.showError);box.append(b)}container.append(box);
  }
  function overviewContent(container,data,previewOnly=false){
    const o=data.overview;
    container.append(el('small',previewOnly?'Preview only · learning position unchanged':o.origin==='teacher'?'Unit overview':'Route summary'),el('h2',data.concept.title));
    if(o.origin==='teacher'){
      container.append(el('p',o.core_problem,'core-question'));
      const steps=el('ol');for(const step of o.steps)steps.append(el('li',String(step)));container.append(steps);
      container.append(el('p',o.prior+'; '+o.next,'muted'),el('p','Afterward you can: '+o.target_ability));
    }else{
      container.append(el('p','Route summary; the first lesson will begin with a specific unit overview.','muted'));
      const next=app.state?.curriculum.concepts.find(c=>c.id===data.next_concept_id);
      container.append(el('p','Prerequisites: '+(data.prerequisites.length?data.prerequisites.map(x=>x.title).join(', '):'No prerequisites specified')),
        el('p','Up next: '+(next?.title||'Final section of this course route')));
    }
    sources(container,data);
  }
  async function showPreview(id){const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(id));preview.replaceChildren();overviewContent(preview,data,true);app.showView('preview');if(matchMedia('(max-width:850px)').matches){nav.hidden=true;document.querySelector('#toggle-nav').setAttribute('aria-expanded','false')}}
  async function update(state){
    const current=state.position?.concept_id||state.curriculum.route[0];
    const hasLesson=state.turns.some(t=>t.channel==='mainline'&&t.concept_id===current&&['completed','running'].includes(t.status));
    const key=JSON.stringify([state.course.id,state.position,state.curriculum,state.sources,hasLesson]);
    if(key===contextKey)return;contextKey=key;const version=++requestVersion;
    nav.replaceChildren(el('small','Learning route'),el('h2','Course contents'),el('p','Click a concept to preview','muted'));
    for(const [i,id] of state.curriculum.route.entries()){
      const c=state.curriculum.concepts.find(c=>c.id===id), b=el('button',String(i+1).padStart(2,'0')+'  '+c.title,'route-item');
      if(id===current){b.classList.add('current');b.setAttribute('aria-current','step')}
      b.onclick=()=>showPreview(id).catch(app.showError);nav.append(b);
    }
    if(!current){overview.replaceChildren(el('p','No learning route has been planned for this course.'));return}
    const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(current));if(version!==requestVersion)return;
    overview.replaceChildren();
    const summary=el('div',null,'position-bar');summary.append(el('small','Current goal'),el('strong',state.position?.goal||data.overview.target_ability),el('span','Next step: '+(state.position?.next_step||'Read the lesson, then try the exercises'),'muted'));overview.append(summary);if(state.position?.progress){const progress=el('details'), title=el('summary','Where you left off');progress.append(title,el('p',state.position.progress));overview.append(progress)}
    const details=el('details',null,'unit-overview'), keySeen='overview:'+state.course.id+':'+current;
    details.open=!hasLesson&&!localStorage.getItem(keySeen);const summaryTitle=el('summary',data.concept.title+(data.overview.origin==='teacher'?' · Unit overview':' · route and sources'));details.append(summaryTitle);
    const content=el('div');overviewContent(content,data);details.append(content);details.addEventListener('toggle',()=>{if(!details.open)localStorage.setItem(keySeen,'seen')});overview.append(details);
    if(state.session.recent_interactions.length){const unanswered=state.session.unanswered_questions.length;overview.prepend(el('p','Continue learning “'+data.concept.title+'”'+(unanswered?' · '+unanswered+' questions awaiting answers':'')+'. Your reading position and unfinished lessons are retained.','resume-note'))}
  }
  // Exact references from the saved interaction win over a later curriculum revision.
  app.events.addEventListener('rendered',async e=>{
    const {node,turn}=e.detail;if(!turn||!/(?:\[Source\s|\[\u6765\u6e90\s)/.test(node.textContent))return;
    let refs=[];try{if(turn.status==='completed')refs=(await app.operation({op:'interaction.read',id:'stream:'+turn.id})).interaction.source_refs;else refs=(await app.operation({op:'curriculum.context',concept_id:turn.concept_id})).sources}catch{return}
    if(!node.isConnected)return;
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),texts=[];while(walker.nextNode())if(!walker.currentNode.parentElement.closest('code,pre,button,.katex'))texts.push(walker.currentNode);
    for(const text of texts){const regex=/\[(?:Source|\u6765\u6e90)\s+([^\s/]+)\s*\/\s*([^\]\s]+)\]/g;let match,last=0;const fragment=document.createDocumentFragment();while((match=regex.exec(text.textContent))){fragment.append(document.createTextNode(text.textContent.slice(last,match.index)));const ref=refs.find(r=>r.source_id===match[1]&&r.unit_id===match[2]);if(ref){const b=el('button','View source','citation');b.onclick=()=>openSource(ref).catch(app.showError);fragment.append(b)}else fragment.append(document.createTextNode(match[0]+' (location pending verification)'));last=regex.lastIndex}if(last){fragment.append(document.createTextNode(text.textContent.slice(last)));text.replaceWith(fragment)}}
  });
  app.events.addEventListener('state',e=>update(e.detail).catch(app.showError));
}
