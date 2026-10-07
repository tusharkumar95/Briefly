const MAX_AGE_MS = 6 * 60 * 60 * 1000;

const PAGE_WORLD = "world";
const PAGE_MARKETS = "markets";
const PAGE_MOVES = "moves";

let state = {
  stories: [],
  page: PAGE_WORLD,
  updated: null,
  moves: []
};

const pageConfig = {
  [PAGE_WORLD]: {
    label: "World",
    title: "Briefly",
    subtitle: "Canada, India and AI — without the noise.",
    sections: [
      ["Canada", "🇨🇦", "Canada"],
      ["India", "🇮🇳", "India"],
      ["AI", "✦", "AI"]
    ]
  },
  [PAGE_MOVES]: {
    label: "Moves",
    title: "Moves",
    subtitle: "Meaningful investor buying from official market disclosures.",
    sections: []
  },
  [PAGE_MARKETS]: {
    label: "Markets",
    title: "Markets",
    subtitle: "The Canadian and Indian market moves worth knowing.",
    sections: [
      ["Canadian Markets", "CA", "Canadian Markets"],
      ["Indian Markets", "IN", "Indian Markets"]
    ]
  }
};

function escapeHTML(value){
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function ageText(date){
  const ms = Date.now() - new Date(date).getTime();

  if(ms < 60 * 1000) return "now";

  const minutes = Math.floor(ms / 60000);
  if(minutes < 60) return `${minutes}m`;

  return `${Math.floor(minutes / 60)}h`;
}

function categoryClass(category){
  return category.toLowerCase().replaceAll(" ", "-");
}

function header(){
  const config = pageConfig[state.page];

  return `
    <header class="top">
      <div class="top-row">
        <div class="brand-mark">BRIEFLY</div>
        <button class="refresh" onclick="loadNews()" aria-label="Refresh news">↻ Refresh</button>
      </div>
      <div class="title">${escapeHTML(config.title)}</div>
      <div class="subtitle">${escapeHTML(config.subtitle)}</div>
    </header>
  `;
}

function nav(){
  return `
    <nav class="bottom-nav" aria-label="Main navigation">
      <button class="nav-btn ${state.page === PAGE_WORLD ? "active" : ""}" onclick="setPage('${PAGE_WORLD}')">
        <span class="nav-icon">◌</span>
        <span>World</span>
      </button>
      <button class="nav-btn ${state.page === PAGE_MARKETS ? "active" : ""}" onclick="setPage('${PAGE_MARKETS}')">
        <span class="nav-icon">↗</span>
        <span>Markets</span>
      </button>
      <button class="nav-btn ${state.page === PAGE_MOVES ? "active" : ""}" onclick="setPage('${PAGE_MOVES}')">
        <span class="nav-icon">◎</span>
        <span>Moves</span>
      </button>
    </nav>
  `;
}

function storyCard(story){
  const title = escapeHTML(story.title);
  const summary = escapeHTML(story.summary || "");
  const source = escapeHTML(story.source || "News");
  const cat = escapeHTML(story.cat || "");
  const time = story.publishedAt ? ageText(story.publishedAt) : "";
  const accent = categoryClass(story.cat || "news");

  return `
    <article class="card ${accent}">
      <div class="accent-dot"></div>
      <div class="card-top">
        <span class="source">${source}</span>
        <span class="time">${time}</span>
      </div>
      <h2 class="card-title">${title}</h2>
      ${summary ? `<p class="card-summary">${summary}</p>` : ""}
      <div class="card-bottom">
        <span class="tag">${cat}</span>
        <span class="read">Briefly</span>
      </div>
    </article>
  `;
}

function sectionBlock(category, icon, label){
  const stories = state.stories.filter(story => story.cat === category);

  return `
    <section class="news-section">
      <div class="section-heading">
        <div class="section-name">
          <span class="section-icon">${icon}</span>
          <span>${escapeHTML(label)}</span>
        </div>
        <span class="section-count">${stories.length}</span>
      </div>
      ${stories.length
        ? stories.map(storyCard).join("")
        : `<div class="empty-section">No fresh stories right now.</div>`}
    </section>
  `;
}

function moveCard(move){
  const qty = Number(move.netBuyQty || 0).toLocaleString("en-IN");
  const price = Number(move.avgBuyPrice || 0).toLocaleString("en-IN");
  const value = Number(move.netBuyValueCr || 0).toLocaleString("en-IN");

  return `
    <article class="card move-card">
      <div class="accent-dot"></div>
      <div class="move-kicker">
        <span class="move-signal">${escapeHTML(move.signal || "Net Purchase")}</span>
        <span class="move-date">${escapeHTML(move.date || "")}</span>
      </div>
      <h2 class="card-title">${escapeHTML(move.company)} <span class="ticker">${escapeHTML(move.symbol)}</span></h2>
      <p class="move-investor">${escapeHTML(move.investor)}</p>
      <div class="move-grid">
        <div><small>NET BOUGHT</small><strong>${qty}</strong></div>
        <div><small>AVG BUY</small><strong>₹${price}</strong></div>
        <div><small>APPROX VALUE</small><strong>₹${value} Cr</strong></div>
      </div>
      <div class="move-source">NSE Bulk Deals · net of same-day disclosed sells</div>
    </article>
  `;
}

function movesView(){
  return `
    <section class="news-section">
      <div class="section-heading">
        <div class="section-name"><span class="section-icon">🇮🇳</span><span>India</span></div>
        <span class="section-count">${state.moves.length}</span>
      </div>
      <div class="moves-note">Official NSE end-of-day disclosures. Calculated from disclosed bulk-deal activity; not real-time brokerage positions.</div>
      ${state.moves.length
        ? state.moves.slice(0, 30).map(moveCard).join("")
        : '<div class="empty-section">No meaningful net purchases in the latest disclosure.</div>'}
    </section>
  `;
}

function render(){
  const config = pageConfig[state.page];

  let html = header();
  html += `<main class="content">`;

  html += state.page === PAGE_MOVES
    ? movesView()
    : config.sections.map(([category, icon, label]) => sectionBlock(category, icon, label)).join("");

  if(state.updated){
    const updatedText = new Date(state.updated).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit"
    });

    html += `
      <div class="fresh">
        ${state.page === PAGE_MOVES ? "NSE end-of-day disclosure feed." : `Updated ${updatedText} · Only stories from the last 6 hours are shown.`}
      </div>
    `;
  }

  html += `</main>${nav()}`;
  document.getElementById("app").innerHTML = html;
}

function setPage(page){
  state.page = page;
  render();
  window.scrollTo({top: 0, behavior: "smooth"});
}

async function loadNews(){
  document.getElementById("app").innerHTML = `
    ${header()}
    <div class="loading">
      <div class="loading-pulse"></div>
      Refreshing your brief…
    </div>
    ${nav()}
  `;

  try{
    const response = await fetch(`data.json?t=${Date.now()}`, {
      cache: "no-store"
    });

    if(!response.ok) throw new Error("Could not load news");

    const data = await response.json();
    const now = Date.now();

    state.updated = data.updated || null;

    try{
      const movesResponse = await fetch(`moves.json?t=${Date.now()}`, {cache: "no-store"});
      if(movesResponse.ok){
        const movesData = await movesResponse.json();
        state.moves = (movesData.records || []).filter(move => !String(move.symbol || "").endsWith("-RE") && Number(move.netBuyValueINR || 0) >= 500000);
      }
    }catch(movesError){
      console.warn("Moves unavailable", movesError);
    }

    state.stories = (data.stories || [])
      .filter(story => {
        if(!story.publishedAt) return false;
        const age = now - new Date(story.publishedAt).getTime();
        return age >= 0 && age <= MAX_AGE_MS;
      })
      .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));

    render();
  }catch(error){
    console.error(error);

    document.getElementById("app").innerHTML = `
      ${header()}
      <div class="empty">
        <strong>Couldn’t refresh Briefly.</strong>
        <br><br>
        Check your connection and try again.
        <br><br>
        <button class="refresh" onclick="loadNews()">↻ Try again</button>
      </div>
      ${nav()}
    `;
  }
}

loadNews();
