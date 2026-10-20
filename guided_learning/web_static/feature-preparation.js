import {bind} from './i18n.js';
export async function setup(app){
  const panel=document.createElement('section');panel.id='preparation-status';panel.setAttribute('aria-live','polite');
  const label=document.createElement('small');const retry=bind(document.createElement('button'),'Retry preparation');retry.className='secondary';retry.hidden=true;
  panel.append(label,retry);app.elements.overview.before(panel);
  let loading=false;
  const labels={running:'Preparing next section',ready:'Preparation ready · learning not yet completed',deferred:'Preparation deferred · your question takes priority',failed:'Preparation failed · main teacher will prepare independently',stale:'Preparation stale · main teacher will prepare independently'};
  async function refresh(){if(loading)return;loading=true;try{const state=await app.api('/api/preparation');const jobs=state.jobs.filter(j=>j.concept_id===state.next_concept_id);const last=jobs.at(-1);bind(label,last?labels[last.status]:'The next section will be prepared when idle');panel.hidden=!state.next_concept_id;retry.hidden=last?.status!=='failed'}catch(e){bind(label,'Preparation status unavailable · you can continue learning')}finally{loading=false}}
  retry.onclick=async()=>{try{await app.api('/api/preparation/schedule',{retry:true});await refresh()}catch(e){app.showError(e)}};
  app.events.addEventListener('state',refresh);app.events.addEventListener('turn',refresh);
  const timer=setInterval(refresh,1500);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});await refresh();
}
