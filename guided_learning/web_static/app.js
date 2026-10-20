import {renderMarkdown} from './render.js';
import {t,bind,localize,setLanguage,getLanguage} from './i18n.js';
export const events = new EventTarget();
export async function api(path,body){const res=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw new Error(t(data.error||'Request failed'));return data}
let state=null;
let stateRequest=0;
const watched=new Map();
const views=new Map();
const viewNames={sources:"Original sources",branches:"Side questions",preview:"Concept preview"};
export const app={api,events,renderMarkdown,showError,t,bind,localize,get language(){return getLanguage()},
  registerView(name,node){views.set(name,{node,scroll:0});node.hidden=true;document.querySelector("#aux-views").append(node);const button=bind(document.createElement("button"),viewNames[name]||name);button.className="secondary";button.onclick=()=>this.showView(name);document.querySelector("#aux-tabs").append(button)},
  showView(name){for(const [key,view] of views){if(!view.node.hidden)view.scroll=this.elements.auxiliary.scrollTop;view.node.hidden=key!==name}this.showAuxiliary();this.elements.auxiliary.scrollTop=views.get(name)?.scroll||0},
get state(){return state},operation:request=>api('/api/operation',request),refresh,
  startTurn:request=>api('/api/turns',request),pauseTurn:id=>api(`/api/turns/${encodeURIComponent(id)}/pause`,{}),
  resumeTurn:id=>api(`/api/turns/${encodeURIComponent(id)}/resume`,{request_id:crypto.randomUUID()}),
  elements:{navigation:document.querySelector('#navigation'),overview:document.querySelector('#overview'),practice:document.querySelector('#practice'),auxiliary:document.querySelector('#auxiliary')},
  showAuxiliary(){this.elements.auxiliary.hidden=false},hideAuxiliary(){this.elements.auxiliary.hidden=true}};
function showError(error){bind(document.querySelector('#error'),error.message)}
const labels={running:'Generating lesson · saved automatically',completed:'Lesson saved · mastery not yet verified',paused:'Paused · lesson unfinished',interrupted:'Connection interrupted · lesson unfinished',failed:'Generation failed · you can regenerate'};
function renderTurn(turn){
  if(turn.channel!=='mainline')return;
  let card=document.getElementById('turn-'+turn.id);
  if(!card){card=document.createElement('article');card.id='turn-'+turn.id;card.innerHTML='<h2 class="lesson-title"></h2><div class="turn-status"></div><div class="lesson-body"></div><div class="turn-controls"></div><details class="past"><summary data-i18n="Earlier unfinished content">Earlier unfinished content</summary><div></div></details>';document.querySelector('#lessons').append(card);localize(card)}
  card.querySelector('.lesson-title').textContent=turn.prompt_snapshot?.context?.concept?.title||state?.curriculum.concepts.find(c=>c.id===turn.concept_id)?.title||turn.concept_id;
  card.classList.toggle('incomplete',turn.status!=='completed');
  bind(card.querySelector('.turn-status'),'{status}{error}',()=>({status:t(labels[turn.status]),error:turn.error?' — '+t(turn.error):''}));
  const body=card.querySelector('.lesson-body');
  if(turn.text){if(body._renderedText!==turn.text){renderMarkdown(body,turn.text);body._renderedText=turn.text;body.removeAttribute('data-localized');events.dispatchEvent(new CustomEvent('rendered',{detail:{node:body,turn}}));}}
  else {body._renderedText=null;delete body.dataset.raw;bind(body,'The teacher is reviewing the current goal and sources…');}
  const controls=card.querySelector('.turn-controls');controls.replaceChildren();
  if(turn.status!=='completed'){const button=bind(document.createElement('button'),turn.status==='running'?'Pause':'Regenerate section');button.onclick=async()=>{try{button.disabled=true;await (turn.status==='running'?app.pauseTurn(turn.id):app.resumeTurn(turn.id));await refresh()}catch(e){showError(e);button.disabled=false}};controls.append(button)}
  const previous=card.querySelector('.past');previous.hidden=!turn.attempts.length;previous.querySelector('div').textContent=turn.attempts.map(a=>a.text).join('\n\n——\n\n');previous.querySelector('div').className='lesson-body';
  if(turn.status==='completed'&&turn.metrics.full_s){const metric=bind(document.createElement('small'),'{status}{error}',()=>({status:t('Full reply {seconds} s',{seconds:turn.metrics.full_s.toFixed(1)}),error:turn.metrics.first_200_chars_s?t(' · first 200 characters {seconds} s',{seconds:turn.metrics.first_200_chars_s.toFixed(1)}):''}));controls.append(metric)}
}
function watch(turn){if(watched.has(turn.id)||turn.status!=='running')return;const source=new EventSource(`/api/turns/${encodeURIComponent(turn.id)}/events`);watched.set(turn.id,source);source.onmessage=e=>{const updated=JSON.parse(e.data);renderTurn(updated);events.dispatchEvent(new CustomEvent('turn',{detail:updated}));if(updated.status!=='running'){source.close();watched.delete(turn.id);refresh().catch(showError)}};source.onerror=()=>bind(document.querySelector('#connection'),'Reconnecting · received content is retained')}
const defaultPrompt='Teach this section fully around the current goal: start with physical intuition, then explain the formulas and necessary derivations, and include an example.';
function applyLanguage(language){const prompt=document.querySelector('#prompt'),wasDefault=prompt.value===t(defaultPrompt);setLanguage(language);if(wasDefault)prompt.value=t(defaultPrompt);document.querySelector('#language').value=getLanguage()}
export async function refresh(){const version=++stateRequest,snapshot=await api('/api/state');if(version!==stateRequest)return state;state=snapshot;applyLanguage(state.preferences.language);document.querySelector('#course-title').textContent=state.course.title;bind(document.querySelector('#connection'),'Course state synced');const select=document.querySelector('#concept');const selected=state.position?.concept_id||state.curriculum.route[0];select.replaceChildren();for(const id of state.curriculum.route){const c=state.curriculum.concepts.find(c=>c.id===id);select.add(new Option(c.title,id))}if(selected)select.value=selected;for(const turn of state.turns){renderTurn(turn);watch(turn)}renderHistory();compactComposer();events.dispatchEvent(new CustomEvent('state',{detail:state}));return state}
document.querySelector('#language').onchange=async event=>{const select=event.target;select.disabled=true;try{await app.operation({op:'preferences.save',language:select.value});await refresh()}catch(e){select.value=getLanguage();showError(e)}finally{select.disabled=false}};
if(matchMedia('(max-width:850px)').matches){app.elements.navigation.hidden=true;document.querySelector('#toggle-nav').setAttribute('aria-expanded','false')}
document.querySelector('#toggle-nav').onclick=()=>{const nav=app.elements.navigation;nav.hidden=!nav.hidden;document.querySelector('#toggle-nav').setAttribute('aria-expanded',String(!nav.hidden))};
document.querySelector('#close-aux').onclick=()=>app.hideAuxiliary();
let composerKey='';
function compactComposer(){
  const current=state.position?.concept_id||state.curriculum.route[0];
  const hasLesson=state.turns.some(t=>t.channel==='mainline'&&t.concept_id===current&&['completed','running'].includes(t.status));
  const key=current+':'+hasLesson, details=document.querySelector('#composer-details');
  if(key!==composerKey){details.open=!hasLesson;composerKey=key}
  bind(details.querySelector('summary'),hasLesson?'Ask a follow-up / reteach this section':'Start current section');
}
function renderHistory(){const container=document.querySelector('#history-list');for(const item of state.session.recent_interactions){if(item.id.startsWith('stream:')||item.id.startsWith('stream-user:')||document.getElementById('history-'+item.id))continue;const card=document.createElement('article');card.id='history-'+item.id;const title=bind(document.createElement('h3'),item.role==='assistant'?'Earlier lessons':'Your question');const body=document.createElement('div');body.className='lesson-body';renderMarkdown(body,item.text);card.append(title,body);container.append(card)}document.querySelector('#course-history').hidden=!container.childElementCount}
document.querySelector('#start').onclick=async()=>{try{bind(document.querySelector('#error'),'');if(!state.position?.concept_id){const first=state.curriculum.concepts.find(c=>c.id===state.curriculum.route[0]);if(!first)throw new Error('Plan a course route first');await app.operation({op:'mainline.enter',request_id:crypto.randomUUID(),concept_id:first.id,goal:first.objective||first.goal||t('Understand {title}',{title:first.title}),next_step:t('Read the lesson, then try the exercises')});await refresh()}await app.startTurn({id:crypto.randomUUID(),concept_id:state.position?.concept_id||state.curriculum.route[0],prompt:document.querySelector('#prompt').value,channel:'mainline'});await refresh()}catch(e){showError(e)}};
try{state=await api('/api/state');applyLanguage(state.preferences.language);for(const path of await api('/features.json')){const feature=await import(path);await feature.setup(app)}await refresh();document.querySelector('#language').disabled=false}catch(e){showError(e)}
