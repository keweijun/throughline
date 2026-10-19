export async function setup(app){
  const panel=document.createElement('section');panel.id='preparation-status';panel.setAttribute('aria-live','polite');
  const label=document.createElement('small');const retry=document.createElement('button');retry.textContent='重试备课';retry.className='secondary';retry.hidden=true;
  panel.append(label,retry);app.elements.overview.before(panel);
  let loading=false;
  const labels={running:'下一小节备课中',ready:'备课就绪 · 尚不代表学习完成',deferred:'备课暂缓 · 优先处理你的提问',failed:'备课失败 · 主教师会自行准备',stale:'备课已过期 · 主教师会自行准备'};
  async function refresh(){if(loading)return;loading=true;try{const state=await app.api('/api/preparation');const jobs=state.jobs.filter(j=>j.concept_id===state.next_concept_id);const last=jobs.at(-1);label.textContent=last?labels[last.status]:'下一小节将在空闲时准备';panel.hidden=!state.next_concept_id;retry.hidden=last?.status!=='failed'}catch(e){label.textContent='备课状态暂不可用 · 不影响继续学习'}finally{loading=false}}
  retry.onclick=async()=>{try{await app.api('/api/preparation/schedule',{retry:true});await refresh()}catch(e){app.showError(e)}};
  app.events.addEventListener('state',refresh);app.events.addEventListener('turn',refresh);
  const timer=setInterval(refresh,1500);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});await refresh();
}
