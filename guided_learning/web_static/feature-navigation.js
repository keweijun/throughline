const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n};
export async function setup(app){
  const nav=app.elements.navigation, overview=app.elements.overview;
  const preview=el('section',null,'preview-view'),sourceView=el('section',null,'source-view');
  app.registerView('preview',preview);app.registerView('sources',sourceView);
  let contextKey='',requestVersion=0;
  async function openSource(ref){
    const data=await app.api('/api/navigation/source?'+new URLSearchParams({source_id:ref.source_id,revision:ref.revision,unit_id:ref.unit_id}));
    sourceView.replaceChildren(el('h2',data.title),el('p',(data.verification==='verified'?'已核验':'待核验 · 请以原页为准')+(data.stale?' · 历史版本':''),'source-status'));
    sourceView.append(el('p','版本 '+data.revision.slice(0,12)+' · '+(data.locator?.page?'第 '+data.locator.page+' 页':data.locator?.line?'第 '+data.locator.line+' 行':'缺少精确定位')));
    if(data.pdf_url){const link=el('a','在新窗口打开原页');link.href=data.pdf_url;link.target='_blank';link.rel='noopener';sourceView.append(link);const frame=el('iframe');frame.title=data.title+' 原页';frame.src=data.pdf_url;sourceView.append(frame)}
    else {const text=el('pre',data.text||'该位置未提取到文字');sourceView.append(text)}
    app.showView('sources');
  }
  app.openSource=openSource;
  function sources(container,data){
    const box=el('div',null,'source-links');box.append(el('h3','来源与核验'));
    if(!data.sources.length)box.append(el('p','尚未关联可定位来源。讲解中的公式和出处仍需核验。','muted'));
    for(const ref of data.sources){const b=el('button',(ref.locator?.page?'原页 '+ref.locator.page:ref.locator?.line?'原文第 '+ref.locator.line+' 行':'定位未提供')+' · '+(ref.verification==='verified'?'已核验':'待核验'),'secondary');b.onclick=()=>openSource(ref).catch(app.showError);box.append(b)}container.append(box);
  }
  function overviewContent(container,data,previewOnly=false){
    const o=data.overview;
    container.append(el('small',previewOnly?'只预览 · 不改变学习位置':o.origin==='teacher'?'单元导览':'路线摘要'),el('h2',data.concept.title));
    if(o.origin==='teacher'){
      container.append(el('p',o.core_problem,'core-question'));
      const steps=el('ol');for(const step of o.steps)steps.append(el('li',String(step)));container.append(steps);
      container.append(el('p',o.prior+'；'+o.next,'muted'),el('p','学完能够：'+o.target_ability));
    }else{
      container.append(el('p','路线摘要；具体单元导览会在首次讲解开头展开。','muted'));
      const next=app.state?.curriculum.concepts.find(c=>c.id===data.next_concept_id);
      container.append(el('p','先修：'+(data.prerequisites.length?data.prerequisites.map(x=>x.title).join('、'):'未指定先修知识')),
        el('p','接下来：'+(next?.title||'本课程路线的最后一节')));
    }
    sources(container,data);
  }
  async function showPreview(id){const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(id));preview.replaceChildren();overviewContent(preview,data,true);app.showView('preview');if(matchMedia('(max-width:850px)').matches){nav.hidden=true;document.querySelector('#toggle-nav').setAttribute('aria-expanded','false')}}
  async function update(state){
    const current=state.position?.concept_id||state.curriculum.route[0];
    const hasLesson=state.turns.some(t=>t.channel==='mainline'&&t.concept_id===current&&['completed','running'].includes(t.status));
    const key=JSON.stringify([state.course.id,state.position,state.curriculum,state.sources,hasLesson]);
    if(key===contextKey)return;contextKey=key;const version=++requestVersion;
    nav.replaceChildren(el('small','学习路线'),el('h2','课程目录'),el('p','点击知识点只预览','muted'));
    for(const [i,id] of state.curriculum.route.entries()){
      const c=state.curriculum.concepts.find(c=>c.id===id), b=el('button',String(i+1).padStart(2,'0')+'  '+c.title,'route-item');
      if(id===current){b.classList.add('current');b.setAttribute('aria-current','step')}
      b.onclick=()=>showPreview(id).catch(app.showError);nav.append(b);
    }
    if(!current){overview.replaceChildren(el('p','课程尚未规划学习路线。'));return}
    const data=await app.api('/api/navigation/preview?concept_id='+encodeURIComponent(current));if(version!==requestVersion)return;
    overview.replaceChildren();
    const summary=el('div',null,'position-bar');summary.append(el('small','当前目标'),el('strong',state.position?.goal||data.overview.target_ability),el('span','下一步：'+(state.position?.next_step||'阅读讲解，再尝试练习'),'muted'));overview.append(summary);if(state.position?.progress){const progress=el('details'), title=el('summary','上次学到哪里');progress.append(title,el('p',state.position.progress));overview.append(progress)}
    const details=el('details',null,'unit-overview'), keySeen='overview:'+state.course.id+':'+current;
    details.open=!hasLesson&&!localStorage.getItem(keySeen);const summaryTitle=el('summary',data.concept.title+(data.overview.origin==='teacher'?' · 单元导览':' · 路线与来源'));details.append(summaryTitle);
    const content=el('div');overviewContent(content,data);details.append(content);details.addEventListener('toggle',()=>{if(!details.open)localStorage.setItem(keySeen,'seen')});overview.append(details);
    if(state.session.recent_interactions.length){const unanswered=state.session.unanswered_questions.length;overview.prepend(el('p','接着学习「'+data.concept.title+'」'+(unanswered?' · '+unanswered+' 个问题待解答':'')+'。你的阅读记录和未完成讲解已保留。','resume-note'))}
  }
  // Exact references from the saved interaction win over a later curriculum revision.
  app.events.addEventListener('rendered',async e=>{
    const {node,turn}=e.detail;if(!turn||!node.textContent.includes('[来源 '))return;
    let refs=[];try{if(turn.status==='completed')refs=(await app.operation({op:'interaction.read',id:'stream:'+turn.id})).interaction.source_refs;else refs=(await app.operation({op:'curriculum.context',concept_id:turn.concept_id})).sources}catch{return}
    if(!node.isConnected)return;
    const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),texts=[];while(walker.nextNode())if(!walker.currentNode.parentElement.closest('code,pre,button,.katex'))texts.push(walker.currentNode);
    for(const text of texts){const regex=/\[来源\s+([^\s/]+)\s*\/\s*([^\]\s]+)\]/g;let match,last=0;const fragment=document.createDocumentFragment();while((match=regex.exec(text.textContent))){fragment.append(document.createTextNode(text.textContent.slice(last,match.index)));const ref=refs.find(r=>r.source_id===match[1]&&r.unit_id===match[2]);if(ref){const b=el('button','查看来源','citation');b.onclick=()=>openSource(ref).catch(app.showError);fragment.append(b)}else fragment.append(document.createTextNode(match[0]+'（定位待核验）'));last=regex.lastIndex}if(last){fragment.append(document.createTextNode(text.textContent.slice(last)));text.replaceWith(fragment)}}
  });
  app.events.addEventListener('state',e=>update(e.detail).catch(app.showError));
}
