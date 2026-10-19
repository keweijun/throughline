export const events = new EventTarget();
export async function api(path,body){const res=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw new Error(data.error||'请求失败');return data}
let state=null;
const watched=new Map();
export const app={api,events,get state(){return state},operation:request=>api('/api/operation',request),refresh,
  startTurn:request=>api('/api/turns',request),pauseTurn:id=>api(`/api/turns/${encodeURIComponent(id)}/pause`,{}),
  resumeTurn:id=>api(`/api/turns/${encodeURIComponent(id)}/resume`,{request_id:crypto.randomUUID()}),
  elements:{navigation:document.querySelector('#navigation'),overview:document.querySelector('#overview'),practice:document.querySelector('#practice'),auxiliary:document.querySelector('#auxiliary')},
  showAuxiliary(){this.elements.auxiliary.hidden=false},hideAuxiliary(){this.elements.auxiliary.hidden=true}};
function showError(error){document.querySelector('#error').textContent=error.message}
const labels={running:'讲解生成中 · 内容自动保存',completed:'讲解已保存 · 不代表已掌握',paused:'已暂停 · 此次讲解未完成',interrupted:'上次连接中断 · 此次讲解未完成',failed:'生成失败 · 可重新生成'};
function renderTurn(turn){
  if(turn.channel!=='mainline')return;
  let card=document.getElementById('turn-'+turn.id);
  if(!card){card=document.createElement('article');card.id='turn-'+turn.id;card.innerHTML='<div class="turn-status"></div><div class="lesson-body"></div><div class="turn-controls"></div><details class="past"><summary>之前未完成的内容</summary><div></div></details>';document.querySelector('#lessons').append(card)}
  card.classList.toggle('incomplete',turn.status!=='completed');
  card.querySelector('.turn-status').textContent=labels[turn.status]+(turn.error?' — '+turn.error:'');
  const body=card.querySelector('.lesson-body');if(body.textContent!==turn.text)body.textContent=turn.text||'老师正在整理当前目标和资料…';
  const controls=card.querySelector('.turn-controls');controls.replaceChildren();
  if(turn.status!=='completed'){const button=document.createElement('button');button.textContent=turn.status==='running'?'停一下':'重新生成本节';button.onclick=async()=>{try{button.disabled=true;await (turn.status==='running'?app.pauseTurn(turn.id):app.resumeTurn(turn.id));await refresh()}catch(e){showError(e);button.disabled=false}};controls.append(button)}
  const previous=card.querySelector('.past');previous.hidden=!turn.attempts.length;previous.querySelector('div').textContent=turn.attempts.map(a=>a.text).join('\n\n——\n\n');previous.querySelector('div').className='lesson-body';
  if(turn.status==='completed'&&turn.metrics.full_s){const metric=document.createElement('small');metric.textContent=`全文 ${turn.metrics.full_s.toFixed(1)} 秒`+(turn.metrics.first_200_chars_s?` · 前 200 字 ${turn.metrics.first_200_chars_s.toFixed(1)} 秒`:'');controls.append(metric)}
}
function watch(turn){if(watched.has(turn.id)||turn.status!=='running')return;const source=new EventSource(`/api/turns/${encodeURIComponent(turn.id)}/events`);watched.set(turn.id,source);source.onmessage=e=>{const updated=JSON.parse(e.data);renderTurn(updated);events.dispatchEvent(new CustomEvent('turn',{detail:updated}));if(updated.status!=='running'){source.close();watched.delete(turn.id);refresh().catch(showError)}};source.onerror=()=>{document.querySelector('#connection').textContent='连接恢复中 · 已收到内容保留'}}
export async function refresh(){state=await api('/api/state');document.querySelector('#course-title').textContent=state.course.title;document.querySelector('#connection').textContent='课程状态已同步';const select=document.querySelector('#concept');const selected=select.value||state.position?.concept_id;select.replaceChildren();for(const id of state.curriculum.route){const c=state.curriculum.concepts.find(c=>c.id===id);select.add(new Option(c.title,id))}if(selected)select.value=selected;for(const turn of state.turns){renderTurn(turn);watch(turn)}events.dispatchEvent(new CustomEvent('state',{detail:state}));return state}
document.querySelector('#start').onclick=async()=>{try{document.querySelector('#error').textContent='';await app.startTurn({id:crypto.randomUUID(),concept_id:document.querySelector('#concept').value,prompt:document.querySelector('#prompt').value,channel:'mainline'});await refresh()}catch(e){showError(e)}};
try{for(const path of await api('/features.json')){const feature=await import(path);await feature.setup(app)}await refresh()}catch(e){showError(e)}
