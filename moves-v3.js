/* Moves v3: dated disclosures, Canadian discovery queue, and persistent stock tracking. */
(function(){
  "use strict";
  const DAY_MS=86400000, MILESTONES=[5,10,15,30];
  const oldView=movesView, oldLoad=loadNews;
  state.movesDaily=null;
  state.movesTracking=null;
  state.moveDate="";
  state.movesPanel="activity";
  state.activeMoveTrack="";
  state.moveMode="All";

  function esc(x){return escapeHTML(x);}
  function fmt(day){
    if(!day)return "—";
    const d=new Date(day+"T12:00:00Z");
    return Number.isFinite(d.getTime())?d.toLocaleDateString("en-CA",{timeZone:"UTC",month:"short",day:"numeric",year:"numeric"}):day;
  }
  function localToday(){
    const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"America/Toronto",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
    const p=Object.fromEntries(parts.map(v=>[v.type,v.value]));
    return p.year+"-"+p.month+"-"+p.day;
  }
  function plusDays(iso,n){return new Date(new Date(iso+"T12:00:00Z").getTime()+n*DAY_MS).toISOString().slice(0,10);}
  function cash(n,market,whole){
    if(n==null||!Number.isFinite(Number(n)))return "—";
    const amount=Number(n),symbol=market==="India"?"₹":"C$";
    return symbol+amount.toLocaleString(market==="India"?"en-IN":"en-CA",{minimumFractionDigits:whole?0:2,maximumFractionDigits:whole?0:4});
  }
  function totalValue(row){
    if(row.market==="India")return "₹"+Number(row.valueCr||row.netBuyValueCr||0).toLocaleString("en-IN",{maximumFractionDigits:2})+" Cr";
    return cash(row.valueCAD||row.value||0,"Canada",true);
  }
  function countBuyers(track){return Number(track.buyers||track.firstBuyerCount||0);}
  function marketIcon(m){return m==="Canada"?"🇨🇦":"🇮🇳";}
  function eventDate(row){return row.day||row.disclosureDate||row.date||"";}
  function statusTag(row){
    const s=String(row.strength||"");
    const score=Number(row.moveScore||0);
    return '<span class="move-strength '+(score>=78?"exceptional":score>=62?"strong":score>=45?"watch":"low")+'">'+esc(s||"Verified")+'</span>';
  }
  function sourceLink(url){return url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">View disclosure ↗</a>':"";}
  function allDays(){return state.movesDaily&&state.movesDaily.days||[];}
  function dayData(){return allDays().find(d=>d.date===state.moveDate)||allDays()[0]||{india:[],canada:[],canadaLeads:[],alerts:[]};}
  function selectedRows(){
    const d=dayData();
    return [...(d.india||[]),...(d.canada||[])].filter(r=>{
      if(state.moveMarket!=="All"&&r.market!==state.moveMarket)return false;
      if(state.investorQuery&&r.investor!==state.investorQuery)return false;
      if(state.companyQuery&&r.company!==state.companyQuery)return false;
      const tags=(r.tags||[]).map(x=>String(x).toLowerCase());
      if(state.moveMode==="Selling")return r.direction==="SELL";
      if(state.moveMode==="Insider Buying")return tags.includes("insider buying");
      if(state.moveMode==="Accumulating")return tags.includes("accumulating");
      if(state.moveMode==="Notable")return Number(r.moveScore||0)>=45;
      return true;
    }).sort((a,b)=>Number(b.moveScore||0)-Number(a.moveScore||0));
  }
  function signalCard(a){
    return '<article class="moves-alert-card"><div class="moves-alert-top"><span>✦ MULTIPLE BUYERS · '+marketIcon(a.market)+' '+esc(a.market)+'</span><span>'+fmt(a.day)+'</span></div>'+
      '<h3>'+esc(a.company||a.symbol)+' <small>'+esc(a.symbol)+'</small></h3>'+
      '<p><strong>'+countBuyers(a)+' distinct buyers</strong> · '+totalValue({...a,market:a.market,valueCAD:a.value,valueCr:a.market==="India"?a.value/1e7:0})+' disclosed purchases</p>'+
      '<div class="moves-alert-buyers">'+esc((a.investors||[]).slice(0,4).join(" · "))+'</div>'+
      '<button type="button" class="moves-track-btn" onclick="selectMoveTrack('+JSON.stringify(a.id).replaceAll('"',"&quot;")+')">View automatic tracking →</button></article>';
  }
  function activityCard(r){
    const price=r.market==="India"?cash(r.avgPrice||r.avgBuyPrice,"India"):cash(r.avgPrice||r.priceCAD,"Canada");
    const qty=Number(r.netQty||r.quantity||r.shares||0).toLocaleString(r.market==="India"?"en-IN":"en-CA");
    const disclosure=r.market==="Canada"&&r.disclosureDate?
      '<span class="moves-small">Disclosed '+fmt(r.disclosureDate)+(r.transactionDate?" · Trade "+fmt(r.transactionDate):" · Trade date unspecified")+'</span>':"";
    return '<article class="card move-card-v2 '+(r.direction==="SELL"?"move-sell":"move-buy")+'"><div class="accent-dot"></div>'+
      '<div class="move-v2-top">'+statusTag(r)+'<span class="move-date">'+marketIcon(r.market)+' '+esc(r.market)+'</span></div>'+
      '<h2 class="card-title">'+esc(r.company||r.symbol)+' <span class="ticker">'+esc(r.symbol||"")+'</span></h2>'+
      '<p class="move-investor">'+esc(r.investor||"")+'</p>'+
      '<div class="move-role">'+esc(r.actorType||r.role||"Disclosed participant")+' · '+esc(r.dealType||"Reported transaction")+'</div>'+
      '<div class="move-grid move-grid-v2"><div><small>'+esc(r.direction==="SELL"?"SOLD":"BOUGHT")+'</small><strong>'+qty+'</strong></div>'+
      '<div><small>DISCLOSED AVG</small><strong>'+price+'</strong></div><div><small>DISCLOSED VALUE</small><strong>'+totalValue(r)+'</strong></div></div>'+
      (r.whyNotable?'<div class="move-why"><small>WHY NOTABLE</small><p>'+esc(r.whyNotable)+'</p></div>':"")+
      '<div class="move-source-v2"><span>'+esc(r.source||"Official/public disclosure")+' '+disclosure+'</span>'+sourceLink(r.sourceUrl)+'</div></article>';
  }
  function leadsView(){
    if(state.moveMarket==="India")return "";
    const leads=allDays().flatMap(d=>d.canadaLeads||[]);
    const archive=state.movesDaily?.canadaArchive||[];
    const last=state.movesDaily?.sourceInfo?.canadaDiscoveryUpdated||"";
    return '<section class="moves-canada-section"><h3>🇨🇦 Canadian disclosure desk <span>'+leads.length+' leads</span></h3>'+
      '<p class="moves-description">Canada is monitored automatically for filings. The following are discovery leads, <strong>not verified purchases</strong>; the source must confirm a completed trade. Latest discovery: '+(last?esc(new Date(last).toLocaleDateString("en-CA")):"unavailable")+'.</p>'+
      (leads.length?leads.slice(0,15).map(x=>'<article class="moves-lead"><span class="moves-lead-label">Needs verification · '+fmt(x.day)+'</span><p>'+esc(x.headline)+'</p>'+sourceLink(x.url)+'</article>').join(""):'<p class="moves-empty">No recent Canadian filing candidates found.</p>')+
      '<details class="moves-archive"><summary>Previously verified Canadian transactions ('+archive.length+')</summary>'+
      (archive.length?archive.map(x=>'<div class="moves-archive-row"><b>'+esc(x.company)+' · '+esc(x.symbol)+'</b><span>Disclosed '+fmt(x.day)+' · '+esc(x.investor)+'</span>'+sourceLink(x.sourceUrl)+'</div>').join(""):'<p>No verified Canadian acquisitions available.</p>')+
      '</details></section>';
  }
  function quotesOf(track){
    const q=state.movesTracking?.quotes?.[track.market+":"+track.symbol]||{};
    return Object.entries(q).filter(([d,p])=>d>=track.day&&d<=localToday()&&d<=plusDays(track.day,45)&&Number.isFinite(Number(p))&&Number(p)>0)
      .map(([d,p])=>({day:d,price:Number(p)})).sort((a,b)=>a.day.localeCompare(b.day));
  }
  function percent(p,baseline){
    if(!baseline||!p)return '<span class="moves-flat">—</span>';
    const n=(p/baseline-1)*100;
    return '<span class="'+(n>=0?"moves-up":"moves-down")+'">'+(n>=0?"+":"")+n.toFixed(2)+'%</span>';
  }
  function milestone(series,day,n){
    const target=plusDays(day,n);
    if(target>localToday())return null;
    return series.find(p=>p.day>=target&&p.day<=plusDays(target,7))||null;
  }
  function detailView(track){
    if(!track)return '<p class="moves-empty">Select a stock above to view its daily price tracking.</p>';
    const series=quotesOf(track);
    const baseline=series.find(p=>p.day===track.day)||null;
    const last=series[series.length-1];
    const quoteSymbol=state.movesTracking?.quoteSymbols?.[track.market+":"+track.symbol];
    const pending=state.movesTracking?.quoteFailures||[];
    const failure=pending.some(x=>x===track.market+":"+track.symbol||x.startsWith(track.market+":"+track.symbol+":"));
    return '<div class="moves-track-detail"><div class="moves-detail-heading"><h3>'+esc(track.company||track.symbol)+' <small>'+esc(track.symbol)+'</small></h3><span>'+marketIcon(track.market)+' '+esc(track.market)+'</span></div>'+
      '<p class="moves-description">Signal: '+fmt(track.day)+' · '+countBuyers(track)+' distinct disclosed buyers. This tracks the market close, NOT their transaction price. A signal is not a buy recommendation.</p>'+
      '<div class="moves-track-stats"><div><small>SIGNAL-DAY CLOSE</small><b>'+cash(baseline?.price,track.market)+'</b></div><div><small>LAST CLOSE</small><b>'+cash(last?.price,track.market)+'</b></div><div><small>CHANGE</small><b>'+percent(last?.price,baseline?.price)+'</b></div></div>'+
      '<div class="moves-table-wrap"><table class="moves-price-table"><thead><tr><th>Checkpoint</th><th>Close</th><th>Change</th><th>Session</th></tr></thead><tbody>'+
      MILESTONES.map(n=>{const p=milestone(series,track.day,n);return '<tr><td>D+'+n+'</td><td>'+cash(p?.price,track.market)+'</td><td>'+percent(p?.price,baseline?.price)+'</td><td>'+(p?fmt(p.day):"Pending")+'</td></tr>';}).join("")+
      '</tbody></table></div>'+
      '<h4>Daily closing prices</h4>'+
      (series.length?'<div class="moves-table-wrap"><table class="moves-price-table"><thead><tr><th>Date</th><th>Close</th><th>Vs signal</th></tr></thead><tbody>'+
      [...series].reverse().map(p=>'<tr><td>'+fmt(p.day)+'</td><td>'+cash(p.price,track.market)+'</td><td>'+percent(p.price,baseline?.price)+'</td></tr>').join("")+'</tbody></table></div>':
      '<p class="moves-empty">Closing prices unavailable yet. Tracking is created, but no unadjusted market close has been confirmed.</p>')+
      '<p class="moves-quote-source">Prices: '+esc(state.movesTracking?.quoteSource||"Awaiting market close feed")+
      (quoteSymbol?" · "+esc(quoteSymbol):"")+(failure?" · Quote unavailable/needs exchange verification":"")+
      (state.movesTracking?.quotesUpdatedAt?" · Refreshed "+esc(new Date(state.movesTracking.quotesUpdatedAt).toLocaleString("en-CA")):"")+'</p></div>';
  }
  function tracksView(){
    const tracks=(state.movesTracking?.tracks||[]).filter(x=>state.moveMarket==="All"||state.moveMarket===x.market);
    const active=tracks.find(x=>x.id===state.activeMoveTrack)||tracks[0];
    if(active&&!state.activeMoveTrack)state.activeMoveTrack=active.id;
    return '<section class="moves-track-sheet"><h3>Automatic Track Sheet</h3><p class="moves-description">Each qualifying multi-buyer signal gets a dated price history, tracked independently as the stock changes. D+5/10/15/30 are calendar-day checkpoints using the next market close.</p>'+
      (tracks.length?'<label class="moves-track-select"><span>Tracked signal</span><select onchange="selectMoveTrack(this.value)">'+tracks.map(x=>'<option value="'+esc(x.id)+'" '+(x.id===active?.id?"selected":"")+'>'+fmt(x.day)+' · '+marketIcon(x.market)+' '+esc(x.symbol)+' · '+countBuyers(x)+' buyers</option>').join("")+'</select></label>'+detailView(active):'<div class="moves-empty">No multi-buyer signals recorded yet.</div>')+'</section>';
  }
  function unreadAlerts(){
    const today=localToday();
    let seen=[];
    try{seen=JSON.parse(localStorage.getItem("briefly-moves-ack-v3")||"[]");if(!Array.isArray(seen))seen=[];}catch(_){}
    return (state.movesDaily?.alerts||[]).filter(a=>a.day===today&&!seen.includes(a.id));
  }
  window.ackMovesAlerts=function(){
    const ids=(state.movesDaily?.alerts||[]).filter(a=>a.day===localToday()).map(a=>a.id);
    try{const older=JSON.parse(localStorage.getItem("briefly-moves-ack-v3")||"[]");localStorage.setItem("briefly-moves-ack-v3",JSON.stringify([...new Set([...(Array.isArray(older)?older:[]),...ids])].slice(-300)));}catch(_){}
    render();
  };
  window.setMoveDate=function(day){if(allDays().some(d=>d.date===day)){state.moveDate=day;render();}};
  window.setMovesPanel=function(panel){state.movesPanel=panel==="tracks"?"tracks":"activity";render();};
  window.selectMoveTrack=function(id){state.activeMoveTrack=id;state.movesPanel="tracks";render();window.scrollTo({top:0,behavior:"smooth"});};
  window.setMoveMode=function(mode){if(["All","Notable","Accumulating","Insider Buying","Selling"].includes(mode)){state.moveMode=mode;render();}};
  window.setMoveMarket=function(m){if(["All","Canada","India"].includes(m)){state.moveMarket=m;render();}};
  moveFilterOptions=function(field){
    return [...new Set(allDays().flatMap(d=>[...(d.india||[]),...(d.canada||[])]).map(r=>String(r[field]||"").trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  };
  movesView=function(){
    if(!state.movesDaily)return '<section class="news-section moves-v2"><div class="moves-empty">Loading seven-day Moves archive…</div>'+oldView()+'</section>';
    if(!allDays().some(d=>d.date===state.moveDate))state.moveDate=allDays()[0]?.date||"";
    const alerts=(dayData().alerts||[]).filter(a=>state.moveMarket==="All"||state.moveMarket===a.market);
    const unread=unreadAlerts();
    const rows=selectedRows();
    const dates=allDays();
    const modes=["All","Notable","Accumulating","Insider Buying","Selling"];
    const opts=(field,selected,handler,placeholder)=>'<label class="moves-filter"><span>'+placeholder+'</span><select onchange="'+handler+'(this.value)"><option value="">All</option>'+moveFilterOptions(field).map(v=>'<option value="'+esc(v)+'" '+(v===selected?"selected":"")+'>'+esc(v)+'</option>').join("")+'</select></label>';
    return '<section class="news-section moves-v3">'+
      '<div class="moves-v3-top"><button class="moves-subtab '+(state.movesPanel==="activity"?"active":"")+'" onclick="setMovesPanel(\'activity\')">Activity</button>'+
      '<button class="moves-subtab '+(state.movesPanel==="tracks"?"active":"")+'" onclick="setMovesPanel(\'tracks\')">Track Sheet <span>'+(state.movesTracking?.tracks?.length||0)+'</span></button></div>'+
      (unread.length?'<div class="moves-new-alert"><b>🔔 '+unread.length+' new multi-buyer signal'+(unread.length===1?"":"s")+' today</b><button onclick="ackMovesAlerts()">Mark seen</button></div>':"")+
      '<div class="move-market-strip">'+["All","Canada","India"].map(m=>'<button class="move-market '+(state.moveMarket===m?"active":"")+'" onclick="setMoveMarket(\''+m+'\')">'+m+'</button>').join("")+'</div>'+
      (state.movesPanel==="tracks"?tracksView():
      '<label class="moves-date-picker"><span>Disclosure date · last 7 days</span><select onchange="setMoveDate(this.value)">'+
      (dates.length?dates.map(d=>'<option value="'+esc(d.date)+'" '+(d.date===state.moveDate?"selected":"")+'>'+fmt(d.date)+' · '+((d.india||[]).length+(d.canada||[]).length)+' verified transactions</option>').join(""):'<option>No activity</option>')+'</select></label>'+
      (alerts.length?'<div class="moves-alert-list"><h3>Multiple buyers detected</h3>'+alerts.map(signalCard).join("")+'</div>':"")+
      '<div class="move-mode-strip">'+modes.map(m=>'<button class="move-mode '+(state.moveMode===m?"active":"")+'" onclick="setMoveMode(\''+m+'\')">'+m+'</button>').join("")+'</div>'+
      '<div class="moves-filters">'+opts("investor",state.investorQuery,"setInvestorFilter","Investor / insider")+opts("company",state.companyQuery,"setCompanyFilter","Company")+'</div>'+
      '<div class="moves-intro"><strong>'+rows.length+' verified disclosures</strong><span>Selected date: '+fmt(state.moveDate)+'. Different buyers on one stock are counted once each.</span></div>'+
      (rows.length?rows.slice(0,80).map(activityCard).join(""):'<div class="moves-empty">No verified disclosures match this date and filter. Try All or another date.</div>')+
      leadsView())+
      '<p class="moves-source-policy">🇮🇳 India: NSE bulk and block deals. 🇨🇦 Canada: confirmed acquisitions only in verified activity; unverified Canadian filings appear in a separate discovery desk. Disclosed purchases are not stock recommendations. Data can be delayed.</p>'+
      '</section>';
  };
  async function refresh(){
    try{
      const stamp="?t="+Date.now();
      const [d,t]=await Promise.all([
        fetch("moves-daily.json"+stamp,{cache:"no-store"}),
        fetch("moves-tracking.json"+stamp,{cache:"no-store"})
      ]);
      if(!d.ok||!t.ok)throw Error("Moves v3 datasets not yet published");
      const daily=await d.json(),tracking=await t.json();
      if(!Array.isArray(daily.days)||!Array.isArray(tracking.tracks))throw Error("Invalid Moves data");
      state.movesDaily=daily;
      state.movesTracking=tracking;
      if(!daily.dates.includes(state.moveDate))state.moveDate=daily.dates[0]||"";
      if(state.page===PAGE_MOVES)render();
    }catch(e){console.warn("Moves v3 unavailable",e);}
  }
  loadNews=async function(){await oldLoad();await refresh();};
  refresh();
})();
