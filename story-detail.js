(() => {
  let historyCache=null;

  async function history(){
    if(historyCache)return historyCache;
    try{
      const response=await fetch(`history.json?t=${Date.now()}`,{cache:"no-store"});
      if(!response.ok)throw new Error("history unavailable");
      historyCache=await response.json();
    }catch{historyCache={snapshots:[]};}
    return historyCache;
  }

  function esc(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));}
  function dateTime(v){try{return new Date(v).toLocaleString(undefined,{month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});}catch{return String(v||"");}}
  function sourceRows(story){
    if(Array.isArray(story.sources)&&story.sources.length)return story.sources.filter(x=>x?.url).slice(0,6);
    return story.url?[{name:story.source||"Source",url:story.url}]:[];
  }

  function timelineFor(data,id){
    const rows=[];
    for(const snapshot of data?.snapshots||[]){
      const story=(snapshot.stories||[]).find(item=>item.id===id);
      if(!story)continue;
      const key=[story.title,story.summary,story.verified,story.sourceCount,story.change].join("|");
      if(rows.length&&rows[rows.length-1].key===key)continue;
      rows.push({key,at:snapshot.at,story});
    }
    return rows.slice(-10).reverse();
  }

  function timelineHTML(rows){
    if(!rows.length)return '<div class="detail-empty">No earlier Briefly snapshot is available for this event yet.</div>';
    return rows.map((row,index)=>{
      const s=row.story;
      const lifecycle=s.lifecycle||s.status||(index===rows.length-1?"New":"Updated");
      return `<article class="timeline-event">
        <div class="timeline-dot"></div>
        <div class="timeline-copy"><div class="timeline-meta"><b>${esc(lifecycle)}</b><span>${esc(dateTime(row.at))}</span></div>
        ${s.change?`<p class="timeline-change">${esc(s.change)}</p>`:""}
        <p>${esc(s.summary||"")}</p>
        <div class="timeline-trust">${s.verified?"✓ Verified":"Source-backed"}${s.sourceCount?` · ${Number(s.sourceCount)} source${Number(s.sourceCount)===1?"":"s"}`:""}</div></div>
      </article>`;
    }).join("");
  }

  async function openDetail(story){
    if(!story)return;
    const existing=document.querySelector("#brieflyStoryDetail");
    if(existing)existing.remove();
    const overlay=document.createElement("div");
    overlay.id="brieflyStoryDetail";
    overlay.className="story-detail-overlay";
    overlay.innerHTML='<div class="story-detail-sheet"><div class="detail-loading">Building event timeline…</div></div>';
    document.body.appendChild(overlay);
    document.body.classList.add("detail-open");
    overlay.addEventListener("click",event=>{if(event.target===overlay||event.target.closest("[data-detail-close]"))closeDetail();});

    const data=await history();
    const rows=timelineFor(data,story.id);
    const sources=sourceRows(story);
    const currentStatus=story.status||story.lifecycle||"Current";
    overlay.querySelector(".story-detail-sheet").innerHTML=`
      <div class="detail-handle"></div>
      <div class="detail-head"><div><p class="detail-kicker">${esc(story.cat||"News")} · ${esc(currentStatus)}</p><h2>${esc(story.title||"")}</h2></div><button type="button" data-detail-close aria-label="Close">×</button></div>
      <section class="detail-current">
        <p class="detail-summary">${esc(story.summary||"")}</p>
        ${story.why?`<div class="detail-why"><small>WHY IT MATTERS</small><p>${esc(story.why)}</p></div>`:""}
        <div class="detail-stats"><span>${story.verified?"✓ Verified":"Source-backed"}</span><span>${Number(story.sourceCount||sources.length||1)} source${Number(story.sourceCount||sources.length||1)===1?"":"s"}</span><span>Score ${Number(story.importanceScore||0).toFixed(1)}</span></div>
      </section>
      <section class="detail-section"><div class="detail-section-title"><h3>What changed</h3><span>Briefly event memory</span></div>${timelineHTML(rows)}</section>
      <section class="detail-section"><div class="detail-section-title"><h3>Sources</h3><span>${sources.length||1} available</span></div>
        <div class="detail-sources">${sources.length?sources.map((source,index)=>`<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer"><span>${index+1}</span><div><b>${esc(source.name||"Source")}</b><small>Open original reporting ↗</small></div></a>`).join(""):'<div class="detail-empty">No direct source link is available.</div>'}</div>
      </section>`;
  }

  function closeDetail(){
    document.querySelector("#brieflyStoryDetail")?.remove();
    document.body.classList.remove("detail-open");
  }
  window.closeBrieflyStoryDetail=closeDetail;

  document.addEventListener("click",event=>{
    if(event.target.closest("a,button,select,input"))return;
    const card=event.target.closest(".intelligence-card");
    if(!card)return;
    const title=card.querySelector(".card-title")?.textContent?.trim();
    const story=(state?.stories||[]).find(item=>String(item.title||"").trim()===title);
    if(story)openDetail(story);
  });

  document.addEventListener("keydown",event=>{if(event.key==="Escape")closeDetail();});
})();
