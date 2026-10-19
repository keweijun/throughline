export async function setup(app){
  const root=app.elements.practice, cards=new Map();
  const heading=document.createElement('h2');heading.textContent='Section practice';
  const status=document.createElement('p'), list=document.createElement('div'), controls=document.createElement('div'), error=document.createElement('p');error.setAttribute('role','alert');
  root.append(heading,status,list,controls,error);
  function button(label,handler){const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{b.disabled=true;error.textContent='';try{await handler();await app.refresh();await refresh()}catch(e){error.textContent=e.message}finally{b.disabled=false}};return b}
  function renderText(el,text){if(app.renderMarkdown)app.renderMarkdown(el,text);else el.textContent=text}
  async function act(task,action,answer){await app.api('/api/practice/action',{id:task.id,action,answer})}
  let updating=false,showAll=false;
  const historyToggle=button('Show all exercises',()=>{showAll=!showAll;historyToggle.textContent=showAll?'Show current and unfinished exercises':'Show all exercises'});
  status.after(historyToggle);
  async function refresh(){
    if(updating||!app.state)return;updating=true;
    try{
      const data=await app.api('/api/practice'), current=app.state.position?.concept_id||app.state.turns.filter(t=>t.channel==='mainline').at(-1)?.concept_id;
      const pending=data.tasks.filter(t=>t.status==='deferred').length;
      status.textContent=`Answers, hints, and independent work are recorded separately. Deferred: ${pending} exercises. Passing is optional before continuing.`;
      for(const task of data.tasks){
        let card=cards.get(task.id);
        if(!card){
          const node=document.createElement('article'), title=document.createElement('h3'), question=document.createElement('div'), history=document.createElement('div'), answer=document.createElement('textarea'), actions=document.createElement('div'), state=document.createElement('p');
          answer.placeholder='Write your reasoning or answer';answer.setAttribute('aria-label','Exercise answer');
          actions.append(button('Give a hint',()=>act(task,'hint')),button('Key steps',()=>act(task,'steps')),button('Full solution',()=>act(task,'solution')),button('Submit answer',()=>act(task,'assess',answer.value)),button('Do later',()=>act(task,'defer')));
          node.append(title,state,question,answer,actions,history);list.append(node);card={node,title,question,history,answer,state,signature:''};cards.set(task.id,card);
        }
        const lastAssessment=task.history.filter(h=>h.action==='assess').at(-1);
        const unresolved=task.status==='pending'||task.status==='deferred'||lastAssessment?.outcome==='needs_work';
        card.node.hidden=!showAll&&task.concept_id!==current&&!unresolved;
        card.title.textContent=(task.origin==='source'?'Source exercise':'Teacher-created exercise')+' · '+(app.state.curriculum.concepts.find(c=>c.id===task.concept_id)?.title||task.concept_id);
        card.state.textContent=task.status==='deferred'?'Deferred; remains pending':lastAssessment?.outcome==='needs_work'?'Needs more practice; remains pending':task.status==='attempted'?'Answered; understanding is subject to teacher assessment':'Awaiting answer';
        renderText(card.question,task.question+(task.source_refs.length?'\n\n'+task.source_refs.map(r=>`[Source ${r.source_id} / ${r.unit_id}]`).join(' '):''));
        const signature=JSON.stringify(task.history);
        if(signature!==card.signature){card.history.replaceChildren();for(const h of task.history){const details=document.createElement('details'), summary=document.createElement('summary'), body=document.createElement('div');summary.textContent=({hint:'Hint',steps:'Key steps',solution:'Full solution',assess:'Teacher assessment'}[h.action])+(h.kind?' · '+({hinted:'Assisted answer',independent:'Independent answer',needs_work:'Needs more practice'}[h.kind]||h.kind):'');details.open=h===task.history.at(-1);renderText(body,h.feedback);details.append(summary,body);card.history.append(details)}card.signature=signature}
      }
      controls.replaceChildren();
      const jobs=data.jobs.filter(j=>!j.processed), active=app.state.turns.filter(t=>t.status==='running');
      for(const job of jobs){const turn=app.state.turns.find(t=>t.id===job.id);const line=document.createElement('p');line.textContent=turn?.status==='running'?'The teacher is preparing exercises or feedback…':turn?.status==='paused'?'Practice generation paused; you can request it again.':turn?.status==='failed'||turn?.status==='interrupted'?'Practice request unfinished; you can request it again.':'';controls.append(line)}
      const failed=data.jobs.filter(j=>j.error);if(failed.length)error.textContent=failed.at(-1).error;
      if(current){
        if(!data.tasks.some(t=>t.concept_id===current)&&!active.some(t=>jobs.some(j=>j.id===t.id&&j.concept_id===current)))controls.append(button('Prepare section exercises',()=>app.api('/api/practice/generate',{concept_id:current})));
        const route=app.state.curriculum.route,index=route.indexOf(current);
        if(index>=0&&index<route.length-1)controls.append(button('Enter next section',()=>app.api('/api/practice/next',{concept_id:current,request_id:crypto.randomUUID()})));
      }
    }finally{updating=false}
  }
  app.events.addEventListener('state',()=>refresh().catch(e=>error.textContent=e.message));
  app.events.addEventListener('turn',e=>{if(e.detail.status!=='running')refresh().catch(err=>error.textContent=err.message)});
  // A completion hook can finish just after the stream's terminal event.
  setInterval(()=>refresh().catch(e=>error.textContent=e.message),2500);
}
