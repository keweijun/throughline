/** Side lane keeps its own DOM, selected passage and scroll anchor. */
export async function setup(app) {
  const panel=document.createElement('section');panel.id='branch-panel';
  panel.innerHTML='<h2>Side questions</h2><p>Ask about a selected sentence or formula. Ordinary questions keep the mainline running.</p><blockquote id="branch-selection"></blockquote><textarea aria-label="Side question" placeholder="What would you like explained?"></textarea><label><input type="checkbox">Pause the mainline first</label><button type="button">Ask</button><p role="status"></p><div class="branch-list"></div>';
  if(app.registerView)app.registerView('branches',panel);else app.elements.auxiliary.append(panel);
  const open=()=>app.showView?app.showView('branches'):app.showAuxiliary();
  const entry=document.createElement('button');entry.textContent='Select a passage / ask a side question';entry.type='button';
  app.elements.overview.before(entry);
  let selection='',selectedTurnId=null,anchor={};let branches=[];const cards=new Map();
  const status=panel.querySelector('[role=status]');
  const contextual=document.createElement('button');contextual.type='button';contextual.textContent='Ask about this passage';contextual.hidden=true;
  Object.assign(contextual.style,{position:'fixed',zIndex:'20',maxWidth:'180px'});document.body.append(contextual);
  const clear=document.createElement('button');clear.type='button';clear.textContent='Clear quote and ask another question';panel.querySelector('blockquote').after(clear);
  function clearSelection(){selection='';selectedTurnId=null;anchor={};panel.querySelector('blockquote').textContent='';contextual.hidden=true;}
  clear.onclick=clearSelection;
  function capture(){
    const selected=window.getSelection();
    if(!selected?.rangeCount||!selected.toString().trim())return;
    const start=selected.anchorNode?.parentElement,end=selected.focusNode?.parentElement;
    if(!start?.closest('#lessons')||!end?.closest('#lessons'))return;
    const lecture=start.closest('#lessons > article');
    if(!lecture||lecture!==end.closest('#lessons > article'))return;
    selectedTurnId=lecture.id.slice('turn-'.length);
    const formula=start.closest('.katex');
    // KaTeX contains both MathML and visual glyphs: preserve its original TeX for a formula-only selection.
    selection=formula&&formula===end.closest('.katex')?(formula.querySelector('annotation[encoding="application/x-tex"]')?.textContent||selected.toString()):selected.toString();
    anchor={scroll_y:window.scrollY};panel.querySelector('blockquote').textContent=selection;
    const rect=selected.getRangeAt(0).getBoundingClientRect();
    contextual.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-190))+'px';
    contextual.style.top=Math.max(8,Math.min(rect.bottom+8,window.innerHeight-48))+'px';contextual.hidden=false;
  }
  document.addEventListener('mouseup',capture);
  document.addEventListener('keyup',event=>{if(event.key==='Shift'||event.key.startsWith('Arrow'))capture();});
  contextual.onpointerdown=event=>event.preventDefault();
  contextual.onclick=()=>{contextual.hidden=true;open();};
  window.addEventListener('scroll',()=>{contextual.hidden=true;},{passive:true});
  // Opening the top entry must never replace a selection-time anchor after scrolling.
  entry.onclick=()=>{contextual.hidden=true;open();};
  function display(node,text){const body=(text||'').split('<teaching-decision>')[0];if(app.renderMarkdown)app.renderMarkdown(node,body);else node.textContent=body;}
  function renderSupplement(card,turn){
    if(!turn)return;
    display(card.querySelector('.supplement'),turn.text);
    const labels={running:'Generating supplement · unfinished',completed:'Supplement saved · mastery not yet verified',paused:'Supplement paused · unfinished',interrupted:'Supplement interrupted · unfinished',failed:'Supplement generation failed · unfinished'};
    card.querySelector('.supplement-status').textContent=labels[turn.status]+(turn.error?' — '+turn.error:'');
    const controls=card.querySelector('.supplement-controls');controls.replaceChildren();
    if(turn.status!=='completed'){
      const button=document.createElement('button');button.textContent=turn.status==='running'?'Pause supplement':'Regenerate supplement';
      button.onclick=async()=>{try{button.disabled=true;await (turn.status==='running'?app.pauseTurn(turn.id):app.resumeTurn(turn.id));await app.refresh();await load();}catch(e){status.textContent=e.message;button.disabled=false;}};
      controls.append(button);
    }
  }
  async function load(){branches=(await app.api('/api/branches')).branches;render();}
  function render(){
    for(const branch of branches){
      let card=cards.get(branch.id);
      if(!card){card=document.createElement('article');card.innerHTML='<h3></h3><blockquote></blockquote><div class="answer"></div><p class="decision"></p><div class="actions"></div><p class="supplement-status" role="status"></p><div class="supplement"></div><div class="supplement-controls"></div>';cards.set(branch.id,card);panel.querySelector('.branch-list').append(card);}
      card.querySelector('h3').textContent=branch.question;card.querySelector('blockquote').textContent=branch.selection;
      const turn=app.state?.turns.find(t=>t.id===branch.turn_id);
      display(card.querySelector('.answer'),turn?.text);
      card.querySelector('.decision').textContent=branch.decision?`${branch.decision.depth==='short'?'Brief answer':'Detailed answer'} · ${branch.decision.rationale}`:(turn?.status==='completed'?'Answer saved, but route decision is missing; the question remains unresolved.':'Waiting for the teacher response and route decision; question saved.');
      const controls=card.querySelector('.actions');controls.replaceChildren();
      const button=(label,action)=>{const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{try{b.disabled=true;await action();await app.refresh();await load();}catch(e){status.textContent=e.message;b.disabled=false;}};controls.append(b);};
      if(branch.status==='suggested'){button('Study the foundations first',()=>app.api('/api/branches/choose',{id:branch.id,choice:'accept'}));button('Continue current topic',()=>app.api('/api/branches/choose',{id:branch.id,choice:'decline'}));}
      if(turn && ['paused','failed','interrupted'].includes(turn.status))button('Answer again',()=>app.resumeTurn(turn.id));
      button('Return to mainline',async()=>{await app.api('/api/branches/return',{id:branch.id});app.hideAuxiliary();window.scrollTo({top:branch.anchor?.scroll_y||0,behavior:'instant'});});
      if(branch.supplement_turn_id){const supplement=app.state?.turns.find(t=>t.id===branch.supplement_turn_id);renderSupplement(card,supplement);}
    }
  }
  panel.querySelector('label').nextElementSibling.onclick=async()=>{try{const q=panel.querySelector('textarea');if(!q.value.trim())return;status.textContent='';const turns=app.state.turns.filter(t=>t.channel==='mainline'&&t.concept_id===app.state.position?.concept_id);const main=turns.at(-1);await app.api('/api/branches/ask',{id:crypto.randomUUID(),question:q.value,selection,selected_turn_id:selectedTurnId,anchor:{...anchor,scroll_y:anchor.scroll_y??window.scrollY},main_turn_id:main?.id,pause:panel.querySelector('input').checked});q.value='';clearSelection();await app.refresh();await load();}catch(e){status.textContent=e.message;}};
  app.events.addEventListener('state',()=>load().catch(e=>status.textContent=e.message));
  app.events.addEventListener('turn',e=>{const turn=e.detail;const branch=branches.find(b=>turn.id===b.turn_id||turn.id===b.supplement_turn_id);if(!branch)return;const card=cards.get(branch.id);if(card){if(turn.id===branch.turn_id)display(card.querySelector('.answer'),turn.text);else renderSupplement(card,turn);}if(turn.status!=='running')load().catch(e=>status.textContent=e.message);});
}
