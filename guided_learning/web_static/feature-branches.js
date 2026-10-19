/** Side lane keeps its own DOM, selected passage and scroll anchor. */
export async function setup(app) {
  const panel=document.createElement('section');panel.id='branch-panel';
  panel.innerHTML='<h2>旁支答疑</h2><p>针对选中的句子或公式提问，普通答疑不打断主线。</p><blockquote id="branch-selection"></blockquote><textarea aria-label="旁支问题" placeholder="哪里没理解？"></textarea><label><input type="checkbox">先停一下主线</label><button type="button">提问</button><p role="status"></p><div class="branch-list"></div>';
  if(app.registerView)app.registerView('branches',panel);else app.elements.auxiliary.append(panel);
  const open=()=>app.showView?app.showView('branches'):app.showAuxiliary();
  const entry=document.createElement('button');entry.textContent='选句提问 / 旁支答疑';entry.type='button';
  app.elements.overview.before(entry);
  let selection='',anchor={};let branches=[];const cards=new Map();
  const status=panel.querySelector('[role=status]');
  function capture(){const s=window.getSelection();if(s && s.toString().trim()){selection=s.toString();anchor={scroll_y:window.scrollY};panel.querySelector('blockquote').textContent=selection;}}
  document.addEventListener('mouseup',()=>{const s=window.getSelection();if(s?.anchorNode?.parentElement?.closest('#lessons'))capture();});
  entry.onclick=()=>{capture();open();};
  function display(node,text){const body=(text||'').split('<teaching-decision>')[0];if(app.renderMarkdown)app.renderMarkdown(node,body);else node.textContent=body;}
  async function load(){branches=(await app.api('/api/branches')).branches;render();}
  function render(){
    for(const branch of branches){
      let card=cards.get(branch.id);
      if(!card){card=document.createElement('article');card.innerHTML='<h3></h3><blockquote></blockquote><div class="answer"></div><p class="decision"></p><div class="actions"></div><div class="supplement"></div>';cards.set(branch.id,card);panel.querySelector('.branch-list').append(card);}
      card.querySelector('h3').textContent=branch.question;card.querySelector('blockquote').textContent=branch.selection;
      const turn=app.state?.turns.find(t=>t.id===branch.turn_id);
      display(card.querySelector('.answer'),turn?.text);
      card.querySelector('.decision').textContent=branch.decision?`${branch.decision.depth==='short'?'简答':'展开'} · ${branch.decision.rationale}`:'等待教师回答及路径判断；问题已保存。';
      const controls=card.querySelector('.actions');controls.replaceChildren();
      const button=(label,action)=>{const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{try{b.disabled=true;await action();await app.refresh();await load();}catch(e){status.textContent=e.message;b.disabled=false;}};controls.append(b);};
      if(branch.status==='suggested'){button('先补一下',()=>app.api('/api/branches/choose',{id:branch.id,choice:'accept'}));button('继续当前内容',()=>app.api('/api/branches/choose',{id:branch.id,choice:'decline'}));}
      if(turn && ['paused','failed','interrupted'].includes(turn.status))button('重新回答',()=>app.resumeTurn(turn.id));
      button('回到主线',async()=>{await app.api('/api/branches/return',{id:branch.id});app.hideAuxiliary();window.scrollTo({top:branch.anchor?.scroll_y||0,behavior:'instant'});});
      if(branch.supplement_turn_id){const supplement=app.state?.turns.find(t=>t.id===branch.supplement_turn_id);display(card.querySelector('.supplement'),supplement?.text);}
    }
  }
  panel.querySelector('button').onclick=async()=>{try{const q=panel.querySelector('textarea');if(!q.value.trim())return;status.textContent='';const turns=app.state.turns.filter(t=>t.channel==='mainline');const main=turns.at(-1);await app.api('/api/branches/ask',{id:crypto.randomUUID(),question:q.value,selection,anchor:{...anchor,scroll_y:anchor.scroll_y??window.scrollY},main_turn_id:main?.id,pause:panel.querySelector('input').checked});q.value='';await app.refresh();await load();}catch(e){status.textContent=e.message;}};
  app.events.addEventListener('state',()=>load().catch(e=>status.textContent=e.message));
  app.events.addEventListener('turn',e=>{const turn=e.detail;const branch=branches.find(b=>turn.id===b.turn_id||turn.id===b.supplement_turn_id);if(!branch)return;const card=cards.get(branch.id);if(card)display(card.querySelector(turn.id===branch.turn_id?'.answer':'.supplement'),turn.text);if(turn.status!=='running')load().catch(e=>status.textContent=e.message);});
}
