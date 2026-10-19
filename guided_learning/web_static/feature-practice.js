export async function setup(app){
  const root=app.elements.practice, cards=new Map();
  const heading=document.createElement('h2');heading.textContent='小节练习';
  const status=document.createElement('p'), list=document.createElement('div'), controls=document.createElement('div'), error=document.createElement('p');error.setAttribute('role','alert');
  root.append(heading,status,list,controls,error);
  function button(label,handler){const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{b.disabled=true;error.textContent='';try{await handler();await app.refresh();await refresh()}catch(e){error.textContent=e.message}finally{b.disabled=false}};return b}
  function renderText(el,text){if(app.renderMarkdown)app.renderMarkdown(el,text);else el.textContent=text}
  async function act(task,action,answer){await app.api('/api/practice/action',{id:task.id,action,answer})}
  let updating=false;
  async function refresh(){
    if(updating||!app.state)return;updating=true;
    try{
      const data=await app.api('/api/practice'), current=app.state.position?.concept_id||app.state.turns.filter(t=>t.channel==='mainline').at(-1)?.concept_id;
      const pending=data.tasks.filter(t=>t.status==='deferred').length;
      status.textContent=`作答、提示与独立完成分别记录。暂缓 ${pending} 题；不要求通过才能继续。`;
      for(const task of data.tasks){
        let card=cards.get(task.id);
        if(!card){
          const node=document.createElement('article'), title=document.createElement('h3'), question=document.createElement('div'), history=document.createElement('div'), answer=document.createElement('textarea'), actions=document.createElement('div'), state=document.createElement('p');
          answer.placeholder='写下你的思路或答案';answer.setAttribute('aria-label','练习作答');
          actions.append(button('给点提示',()=>act(task,'hint')),button('关键步骤',()=>act(task,'steps')),button('完整解答',()=>act(task,'solution')),button('提交作答',()=>act(task,'assess',answer.value)),button('稍后做',()=>act(task,'defer')));
          node.append(title,state,question,answer,actions,history);list.append(node);card={node,title,question,history,answer,state,signature:''};cards.set(task.id,card);
        }
        card.node.hidden=task.concept_id!==current&&task.status!=='deferred';
        card.title.textContent=(task.origin==='source'?'来源练习':'教师自编练习')+' · '+task.concept_id;
        card.state.textContent=task.status==='deferred'?'已暂缓，仍保留待办':task.status==='attempted'?'已作答，掌握情况以教师评估为准':'待作答';
        renderText(card.question,task.question+(task.source_refs.length?'\n\n'+task.source_refs.map(r=>`[来源 ${r.source_id} / ${r.unit_id}]`).join(' '):''));
        const signature=JSON.stringify(task.history);
        if(signature!==card.signature){card.history.replaceChildren();for(const h of task.history){const details=document.createElement('details'), summary=document.createElement('summary'), body=document.createElement('div');summary.textContent=({hint:'提示',steps:'关键步骤',solution:'完整解答',assess:'教师评估'}[h.action])+(h.kind?' · '+({hinted:'有帮助作答',independent:'独立作答',needs_work:'仍需练习'}[h.kind]||h.kind):'');details.open=h===task.history.at(-1);renderText(body,h.feedback);details.append(summary,body);card.history.append(details)}card.signature=signature}
      }
      controls.replaceChildren();
      const jobs=data.jobs.filter(j=>!j.processed), active=app.state.turns.filter(t=>t.status==='running');
      for(const job of jobs){const turn=app.state.turns.find(t=>t.id===job.id);const line=document.createElement('p');line.textContent=turn?.status==='running'?'教师正在准备题目或反馈…':turn?.status==='paused'?'练习生成已暂停，可再次请求。':turn?.status==='failed'||turn?.status==='interrupted'?'练习请求未完成，可再次请求。':'';controls.append(line)}
      const failed=data.jobs.filter(j=>j.error);if(failed.length)error.textContent=failed.at(-1).error;
      if(current){
        if(!data.tasks.some(t=>t.concept_id===current)&&!active.some(t=>jobs.some(j=>j.id===t.id&&j.concept_id===current)))controls.append(button('准备本节练习',()=>app.api('/api/practice/generate',{concept_id:current})));
        const route=app.state.curriculum.route,index=route.indexOf(current);
        if(index>=0&&index<route.length-1)controls.append(button('进入下一小节',()=>app.api('/api/practice/next',{concept_id:current,request_id:crypto.randomUUID()})));
      }
    }finally{updating=false}
  }
  app.events.addEventListener('state',()=>refresh().catch(e=>error.textContent=e.message));
  app.events.addEventListener('turn',e=>{if(e.detail.status!=='running')refresh().catch(err=>error.textContent=err.message)});
  // A completion hook can finish just after the stream's terminal event.
  setInterval(()=>refresh().catch(e=>error.textContent=e.message),2500);
}
