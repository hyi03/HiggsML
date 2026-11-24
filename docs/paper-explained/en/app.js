/* Offline presentation navigation. Hashes are stable, shareable page positions. */
(() => {
  'use strict';
  const slides=SLIDES,count=slides.length,deck=document.querySelector('#deck'),toc=document.querySelector('#toc');
  document.querySelector('#page').max=count;
  document.querySelector('#page-count').textContent=count;
  document.querySelector('#toc-title').textContent=`${count}-slide learning route`;
  const sourceLink=s=>`<a href="../../paper/latex/main.tex" target="_blank" rel="noopener">${s.source}</a>${s.figure?` · <a href="../../paper/latex/figures/${s.figure}.pdf" target="_blank" rel="noopener">Original figure PDF</a>`:''}`;
  deck.innerHTML=slides.map((s,i)=>`<section class="slide" id="slide-${i+1}" aria-labelledby="title-${i+1}"${i?' hidden':''}><header class="slide-header"><p class="section-label">${s.chapter}</p><${i?'h2':'h1'} id="title-${i+1}">${s.title}</${i?'h2':'h1'}><p class="lead">${s.lead}</p></header><div class="slide-body">${s.body}</div><footer class="slide-footer"><span>${sourceLink(s)}</span><span>Educational MC study · exploratory ${String(i+1).padStart(2,'0')} / ${count}</span></footer></section>`).join('');
  document.querySelector('#toc-list').innerHTML=slides.map((s,i)=>`<li><a href="#slide-${i+1}"><span>${String(i+1).padStart(2,'0')}</span>${s.title}</a></li>`).join('');
  Widgets.mount();
  let current=1,notesOpen=true;
  const clamp=n=>Math.max(1,Math.min(count,Number.isFinite(n)?Math.round(n):1));
  const fromHash=()=>clamp(Number(location.hash.match(/^#slide-(\d+)$/)?.[1]||1));
  function render(){current=fromHash();document.querySelectorAll('.slide').forEach((s,i)=>s.hidden=i+1!==current);
    const languageLink=document.querySelector('#language-link');if(languageLink)languageLink.href=`${languageLink.dataset.target}#slide-${current}`;
    document.querySelector('#page').value=current;document.querySelector('#prev').disabled=current===1;document.querySelector('#next').disabled=current===count;
    document.querySelector('#chapter-status').textContent=slides[current-1].chapter;
    document.querySelector('#progress-fill').style.width=`${current/count*100}%`;
    document.querySelector('#announcement').textContent=`Slide ${current} of ${count}. ${slides[current-1].title}`;
    document.title=`${current}/${count} ${slides[current-1].title} · HiggsML paper explained`;
    document.querySelector('#notes-button').setAttribute('aria-expanded',String(notesOpen));
    document.querySelectorAll('#toc-list a').forEach((a,i)=>i+1===current?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current'));
    const notes=document.querySelector('#notes');notes.innerHTML=`<div class="notes-head"><h2>${current}. ${slides[current-1].title}</h2><button id="notes-close">Collapse explanation</button></div>${slides[current-1].notes}<p class="source-links">${sourceLink(slides[current-1])}</p>`;notes.hidden=!notesOpen;document.querySelector('#notes-close').addEventListener('click',()=>toggleNotes(false));
  }
  function go(n){n=clamp(n);if(n===current){render();return;}location.hash=`slide-${n}`;window.scrollTo({top:0,behavior:'instant'});}
  function toggleNotes(force){notesOpen=force===undefined?!notesOpen:force;document.querySelector('#notes').hidden=!notesOpen;document.querySelector('#notes-button').setAttribute('aria-expanded',String(notesOpen));if(notesOpen)document.querySelector('#notes').scrollIntoView({block:'start',behavior:'instant'});else{window.scrollTo({top:0,behavior:'instant'});document.querySelector('#notes-button').focus();}}
  document.querySelector('#prev').addEventListener('click',()=>go(current-1));document.querySelector('#next').addEventListener('click',()=>go(current+1));
  document.querySelector('#page').addEventListener('change',e=>go(Number(e.target.value)));
  document.querySelector('#page').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();go(Number(e.target.value));}});
  document.querySelector('#jump').addEventListener('click',()=>go(Number(document.querySelector('#page').value)));
  document.querySelector('#notes-button').addEventListener('click',()=>toggleNotes());
  document.querySelector('#toc-button').addEventListener('click',()=>toc.showModal());document.querySelector('#toc-close').addEventListener('click',()=>toc.close());
  toc.addEventListener('click',e=>{if(e.target.closest('a'))toc.close();});
  document.querySelector('#full-button').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{document.querySelector('#announcement').textContent='Fullscreen is unavailable here. Use the browser fullscreen menu.';document.querySelector('#full-button').textContent='Use browser fullscreen';}});
  document.addEventListener('fullscreenchange',()=>document.querySelector('#full-button').textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen');
  document.querySelector('#print-button').addEventListener('click',()=>setTimeout(()=>window.print(),0));
  document.addEventListener('keydown',e=>{if(toc.open||e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,select,textarea,button,a,summary,[contenteditable="true"]'))return;
    const keys={ArrowRight:current+1,PageDown:current+1,ArrowLeft:current-1,PageUp:current-1,Home:1,End:count};if(e.key in keys){e.preventDefault();go(keys[e.key]);}else if(e.key===' '){e.preventDefault();go(current+(e.shiftKey?-1:1));}});
  window.addEventListener('hashchange',render);render();
})();
