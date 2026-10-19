// Libraries are bundled locally; no runtime CDN or third-party image requests.
export function renderMarkdown(node,text){
  if(node.dataset.raw===text)return;
  const math=[];const token='MATH'+crypto.randomUUID().replaceAll('-','');
  const prepared=String(text).replace(/(```[\s\S]*?```|`[^`\n]*`)|(\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^$\n]+?)\$)/g,(whole,code,expression,a,b,c,d)=>{
    if(code)return code;const index=math.length;math.push({tex:a??b??c??d,display:a!==undefined||b!==undefined});return token+index+'END';
  });
  const fragment=DOMPurify.sanitize(marked.parse(prepared),{RETURN_DOM_FRAGMENT:true,USE_PROFILES:{html:true},FORBID_TAGS:['img','style','iframe','form','input','button','video','audio'],FORBID_ATTR:['style','id'],ALLOW_DATA_ATTR:false});
  const walker=document.createTreeWalker(fragment,NodeFilter.SHOW_TEXT),texts=[];while(walker.nextNode())texts.push(walker.currentNode);
  for(const textNode of texts){let match,last=0;const pattern=new RegExp(token+'(\\d+)END','g'),result=document.createDocumentFragment();while((match=pattern.exec(textNode.textContent))){result.append(document.createTextNode(textNode.textContent.slice(last,match.index)));const item=math[Number(match[1])],span=document.createElement('span');span.dataset.tex=item.tex;try{katex.render(item.tex,span,{displayMode:item.display,throwOnError:false,trust:false,maxExpand:1000,maxSize:20})}catch{span.textContent=item.tex}result.append(span);last=pattern.lastIndex}if(last){result.append(document.createTextNode(textNode.textContent.slice(last)));textNode.replaceWith(result)}}
  for(const link of fragment.querySelectorAll('a')){const href=link.getAttribute('href')||'';if(!/^(https?:\/\/|#)/i.test(href))link.removeAttribute('href');else{link.target='_blank';link.rel='noopener noreferrer'}}
  // Keep unchanged blocks alive while later paragraphs stream, preserving selection.
  const scrollY=window.scrollY;const incoming=[...fragment.childNodes];
  incoming.forEach((child,index)=>{const old=node.childNodes[index];if(!old)node.append(child);else if(!old.isEqualNode(child))old.replaceWith(child)});
  while(node.childNodes.length>incoming.length)node.lastChild.remove();
  node.dataset.raw=text;node.classList.add('markdown');if(window.scrollY!==scrollY)window.scrollTo(window.scrollX,scrollY);
}
