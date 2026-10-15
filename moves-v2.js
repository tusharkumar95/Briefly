(() => {
  const MOVE_MODES=["Notable","Accumulating","Insider Buying","Selling"];
  const MOVE_MARKETS=["All","Canada","India"];
  pageConfig[PAGE_MOVES]={title:"Moves",subtitle:"Meaningful ownership activity from official and verified public disclosures."};
  state.movesV2=[];
  state.moveMode="Notable";
  state.moveMarket="All";
  state.movesMeta={};

  function money(move){
    if(move.market==="India") return `₹${Number(move.valueCr||0).toLocaleString("en-IN",{maximumFractionDigits:2})} Cr`;
    return Number(move.valueCAD||0).toLocaleString("en-CA",{style:"currency",currency:"CAD",maximumFractionDigits:0});
  }
  function price(move){
    const n=Number(move.avgPrice||0);
    if(!n)return "—";
    return move.market==="India"?`₹${n.toLocaleString("en-IN",{maximumFractionDigits:2})}`:`C$${n.toLocaleString("en-CA",{maximumFractionDigits:4})}`;
  }
  function quantity(move){return Number(move.netQty||move.quantity||0).toLocaleString(move.market==="India"?"en-IN":"en-CA");}
  function modeMatch(move){
    const tags=(move.tags||[]).map(x=>String(x).toLowerCase());
    if(state.moveMode==="Accumulating")return tags.includes("accumulating");
    if(state.moveMode==="Insider Buying")return tags.includes("insider buying");
    if(state.moveMode==="Selling")return move.direction==="SELL"||tags.includes("selling");
    return Number(move.moveScore||0)>=45;
  }
  function filtersMatch(move){
    if(state.moveMarket!=="All"&&move.market!==state.moveMarket)return false;
    if(state.investorQuery&&move.investor!==state.investorQuery)return false;
    if(state.companyQuery&&move.company!==state.companyQuery)return false;
    return modeMatch(move);
  }
  function scoreClass(score){return score>=78?"exceptional":score>=62?"strong":score>=45?"watch":"low";}
  function card(move){
    const score=Number(move.moveScore||0);
    const days=Number(move.observedDays||1);
    const source=move.source||move.dealType||"Public disclosure";
    const role=move.role||move.actorType||"Investor";
    const date=move.transactionDate||move.date||move.disclosureDate||"";
    const direction=move.direction==="SELL"?"Sold":"Bought";
    const sourceLink=move.sourceUrl?`<a href="${escapeHTML(move.sourceUrl)}" target="_blank" rel="noopener noreferrer">Source ↗</a>`:"";
    return `<article class="card move-card-v2 ${move.direction==="SELL"?"move-sell":"move-buy"}">
      <div class="accent-dot"></div>
      <div class="move-v2-top"><div class="move-v2-badges"><span class="move-strength ${scoreClass(score)}">${escapeHTML(move.strength||"Worth watching")}</span><span class="move-score">${score}/100</span></div><span class="move-date">${escapeHTML(date)}</span></div>
      <h2 class="card-title">${escapeHTML(move.company||"")} <span class="ticker">${escapeHTML(move.symbol||"")}</span></h2>
      <p class="move-investor">${escapeHTML(move.investor||"")}</p>
      <div class="move-role">${escapeHTML(role)} · ${escapeHTML(move.dealType||"Disclosed transaction")}</div>
      <div class="move-grid move-grid-v2">
        <div><small>${direction.toUpperCase()}</small><strong>${quantity(move)}</strong></div>
        <div><small>AVG PRICE</small><strong>${price(move)}</strong></div>
        <div><small>VALUE</small><strong>${money(move)}</strong></div>
      </div>
      <div class="move-pattern"><span>${escapeHTML(move.signal||direction)}</span>${days>1?`<b>${days} observed days</b>`:"<b>First observed</b>"}</div>
      ${move.whyNotable?`<div class="move-why"><small>WHY NOTABLE</small><p>${escapeHTML(move.whyNotable)}</p></div>`:""}
      <div class="move-source-v2"><span>${escapeHTML(source)}</span>${sourceLink}</div>
    </article>`;
  }

  window.setMoveMode=value=>{if(MOVE_MODES.includes(value)){state.moveMode=value;render();}};
  window.setMoveMarket=value=>{if(MOVE_MARKETS.includes(value)){state.moveMarket=value;render();}};
  moveFilterOptions=function(field){
    return [...new Set((state.movesV2||[]).map(move=>String(move[field]||"").trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:"base"}));
  };

  movesView=function(){
    const investorOptions=moveFilterOptions("investor"), companyOptions=moveFilterOptions("company");
    const filtered=(state.movesV2||[]).filter(filtersMatch).sort((a,b)=>(Number(b.moveScore||0)-Number(a.moveScore||0))||String(b.date||"").localeCompare(String(a.date||"")));
    const shown=(state.investorQuery||state.companyQuery)?filtered:filtered.slice(0,18);
    const sourceNote=state.movesMeta?.sources?.Canada?.automation||"Canadian records are published only when independently verified.";
    return `<section class="news-section moves-v2">
      <div class="move-mode-strip">${MOVE_MODES.map(mode=>`<button class="move-mode ${state.moveMode===mode?"active":""}" onclick="setMoveMode('${mode}')">${mode}</button>`).join("")}</div>
      <div class="move-market-strip">${MOVE_MARKETS.map(market=>`<button class="move-market ${state.moveMarket===market?"active":""}" onclick="setMoveMarket('${market}')">${market}</button>`).join("")}</div>
      <div class="moves-intro"><strong>${shown.length} signals</strong><span>Ranked by size, repetition, transaction type, participant type and source quality.</span></div>
      <div class="moves-filters">
        <label class="moves-filter"><span>Investor / insider</span><select onchange="setInvestorFilter(this.value)"><option value="">All</option>${investorOptions.map(v=>`<option value="${escapeHTML(v)}" ${v===state.investorQuery?"selected":""}>${escapeHTML(v)}</option>`).join("")}</select></label>
        <label class="moves-filter"><span>Company</span><select onchange="setCompanyFilter(this.value)"><option value="">All</option>${companyOptions.map(v=>`<option value="${escapeHTML(v)}" ${v===state.companyQuery?"selected":""}>${escapeHTML(v)}</option>`).join("")}</select></label>
      </div>
      ${(state.investorQuery||state.companyQuery)?`<div class="filter-status">${filtered.length} matching moves <button class="moves-reset" onclick="clearMoveFilters()">Clear ×</button></div>`:""}
      ${shown.length?shown.map(card).join(""):'<div class="empty-section">No moves match this signal view right now.</div>'}
      <div class="moves-source-policy"><b>Source policy</b><p>India uses official NSE bulk and block disclosures. Canada uses SEDI/primary public disclosures only after verification. ${escapeHTML(sourceNote)}</p></div>
    </section>`;
  };

  async function refreshMovesV2(){
    try{
      const response=await fetch(`moves-intelligence.json?t=${Date.now()}`,{cache:"no-store"});
      if(!response.ok)return;
      const data=await response.json();
      state.movesV2=Array.isArray(data.records)?data.records:[];
      state.movesMeta=data;
      if(state.page===PAGE_MOVES)render();
    }catch(error){console.warn("Moves Intelligence v2 unavailable",error);}
  }

  const priorLoad=loadNews;
  loadNews=async function(){
    await priorLoad();
    await refreshMovesV2();
  };
  refreshMovesV2();
})();
