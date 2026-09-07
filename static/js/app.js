const form=document.querySelector('#chatForm'),input=document.querySelector('#message'),send=document.querySelector('#send'),conversation=document.querySelector('#conversation'),dialog=document.querySelector('#dataDialog');
const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function addMessage(role,html,id=''){const wrap=document.createElement('div');wrap.className=`message ${role}`;if(id)wrap.id=id;wrap.innerHTML=`<div class="avatar"><i class="bi ${role==='user'?'bi-person-fill':'bi-stars'}"></i></div><div class="bubble">${html}</div>`;conversation.appendChild(wrap);conversation.scrollTop=conversation.scrollHeight;return wrap}
function tableHtml(columns,rows){return `<div class="preview"><table class="table table-sm"><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(c=>`<td>${r[c]===null?'—':esc(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
function renderStructuredResult(data){const sources=data.sources.map(s=>`<div class="result-line ${s.status==='success'?'':'warn'}"><i class="bi ${s.status==='success'?'bi-check-circle-fill':'bi-exclamation-triangle-fill'}"></i><div><b>${esc(s.metric)} — ${esc(s.name)}</b>${s.aggregation?`<small>${esc(s.aggregation)}</small>`:''}${s.message?`<small>${esc(s.message)}</small>`:''}</div></div>`).join('');const ctx=data.context;const html=`<b>AI Data Consultant</b><p class="result-summary">${esc(data.message)}</p><span class="source-badge structured">📊 STRUCTURED DATA</span><div class="source-results">${sources}</div>${tableHtml(data.columns,data.preview)}<div class="context-strip">${esc(ctx.countries.join(', '))} · ${esc(ctx.metrics.join(', '))} · ${ctx.start_year}–${ctx.end_year}</div><div class="actions"><button class="view-data"><i class="bi bi-table"></i> View Full Data</button><a class="primary" href="/api/download/${data.download_token}/excel"><i class="bi bi-file-earmark-excel"></i> Download Excel</a><a href="/api/download/${data.download_token}/csv"><i class="bi bi-filetype-csv"></i> Download CSV</a></div>`;const msg=addMessage('assistant',html);msg.querySelector('.view-data').onclick=()=>openData(data.columns,data.data);return msg}
function renderFriendlyError(data){const chips=(data.suggestions||[]).map(value=>`<button>${esc(value)}</button>`).join('');addMessage('assistant',`<b>AI Data Consultant</b><div class="help-card"><i class="bi bi-compass"></i><div><p>${esc(data.error||'I need a little more detail to prepare that report.')}</p>${chips?`<small>Try one of these:</small><div class="suggestions">${chips}</div>`:''}</div></div>`)}
function openData(columns,rows){document.querySelector('#fullHead').innerHTML=`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`;document.querySelector('#fullBody').innerHTML=rows.map(r=>`<tr>${columns.map(c=>`<td>${r[c]===null?'—':esc(r[c])}</td>`).join('')}</tr>`).join('');dialog.showModal()}
function validSourceUrl(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password}catch{return false}}
function renderResult(data){
  const msg=data.excel_available?renderStructuredResult(data):addMessage('assistant','<b>AI Data Consultant</b>');
  const bubble=msg.querySelector('.bubble');
  if(data.structured_error){const p=document.createElement('p');p.textContent=data.structured_error;bubble.appendChild(p)}
  if(!data.web)return;
  const web=data.web,section=document.createElement('section');section.className='web-research';
  const results=web.results.filter(r=>validSourceUrl(r.url));
  section.innerHTML=`<span class="source-badge web">🌐 WEB RESEARCH</span><p>${esc(web.message)}</p><small>Search query: ${esc(web.query)}</small>${results.length?`<p>✓ Found ${results.length} relevant sources</p><p class="research-notice">Search snippets are not verified facts. Review the original sources.</p>`:''}<div class="web-results">${results.map((r,i)=>`<article class="web-result"><span class="source-badge web">🌐 ${esc(r.category)}</span><h3>${i+1}. ${esc(r.title)}</h3><small>${esc(r.domain)}${r.published_date?' · '+esc(r.published_date):''}</small><p>${esc(r.snippet)}</p><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open Source ↗</a></article>`).join('')}</div><details class="web-sources"><summary>Sources (${results.length})</summary>${results.map((r,i)=>`<p><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">[${i+1}] ${esc(r.title)}</a><br><small>${esc(r.domain)}</small></p>`).join('')}</details><div class="actions"><button class="view-sources">View Sources</button><button class="search-again">Search Again</button>${web.download_token?`<a href="/api/download/${encodeURIComponent(web.download_token)}/excel">Export Research Excel</a><a href="/api/download/${encodeURIComponent(web.download_token)}/csv">Export Research CSV</a>`:''}</div>`;
  bubble.appendChild(section);
  section.querySelector('.view-sources').onclick=()=>{const details=section.querySelector('details');details.open=true;details.scrollIntoView({behavior:'smooth',block:'nearest'})};
  section.querySelector('.search-again').onclick=()=>submit(web.query,true);
}
async function submit(message,researchOnly=false){
  if(send.disabled)return;
  addMessage('user',`<b>You</b><p>${esc(message)}</p>`);input.value='';input.style.height='auto';send.disabled=true;document.querySelector('#newChat').disabled=true;
  const thinking=addMessage('assistant','<div class="thinking"><div class="dots"><span></span> <span></span> <span></span></div><span class="progress-text">Understanding request...</span></div>');
  let timer;
  try{
    const options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,research_only:researchOnly})};
    const planned=await fetch('/api/chat/plan',options);const plan=await planned.json();
    if(!planned.ok){renderFriendlyError(plan);return}
    let step=0;const label=thinking.querySelector('.progress-text');
    timer=setInterval(()=>{step=Math.min(step+1,plan.steps.length-1);label.textContent=plan.steps[step]},1000);
    const response=await fetch('/api/chat',options);const data=await response.json();
    if(!response.ok||!data.success){renderFriendlyError(data);return}
    renderResult(data);
    conversation.scrollTop=conversation.scrollHeight;
  }catch(error){renderFriendlyError({error:'I could not reach the data service just now. Please try again.',suggestions:[message]})}
  finally{clearInterval(timer);thinking.remove();send.disabled=false;document.querySelector('#newChat').disabled=false;input.focus()}
}
form.onsubmit=e=>{e.preventDefault();const message=input.value.trim();if(message)submit(message)};input.oninput=()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,120)+'px'};input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}};
document.addEventListener('click',e=>{const suggestion=e.target.closest('.suggestions button');if(suggestion){input.value=suggestion.textContent;form.requestSubmit()}});document.querySelector('#closeDialog').onclick=()=>dialog.close();
document.querySelector('#newChat').onclick=async()=>{await fetch('/api/chat/reset',{method:'POST'});conversation.innerHTML='';addMessage('assistant','<b>AI Data Consultant</b><p>New chat started. What public data would you like to combine?</p>');input.focus()};
fetch('/api/sources').then(r=>r.json()).then(data=>{document.querySelector('#sourceStatus').innerHTML=data.sources.map(s=>`<div class="source-line ${s.available?'':'off'}"><i></i><b>${esc(s.name)}</b><small>${esc(s.message)}</small></div>`).join('')}).catch(()=>{document.querySelector('#sourceStatus').textContent='Status unavailable'});
