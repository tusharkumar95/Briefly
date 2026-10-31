const MAX_AGE_MS = 24 * 60 * 60 * 1000;

const PAGE_WORLD = "world";
const PAGE_MARKETS = "markets";

let state = {
  stories: [],
  page: PAGE_WORLD,
  worldFilter: "All",
  updated: null,
  engine: "",
  editor: ""
};

const pageConfig = {
  [PAGE_WORLD]: {
    title: "Briefly",
    subtitle: "What actually happened — ranked, condensed and stripped of the noise."
  },
  [PAGE_MARKETS]: {
    title: "Markets",
    subtitle: "The Canadian and Indian market developments worth knowing."
  }
};

const WORLD_FILTERS = ["All", "World", "Canada", "India", "AI"];

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
  if(!Number.isFinite(ms)) return "";
  if(ms < 60 * 1000) return "now";
  const minutes = Math.max(0, Math.floor(ms / 60000));
  if(minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h` : `${Math.floor(hours / 24)}d`;
}

function categoryClass(category){
  return String(category || "news").toLowerCase().replaceAll(" ", "-");
}

function header(){
  const config = pageConfig[state.page];
  const intelligent = state.engine ? `<span class="engine-pill">${escapeHTML(state.engine)}</span>` : "";
  return `
    <header class="top">
      <div class="top-row">
        <div class="brand-line"><div class="brand-mark">BRIEFLY</div>${intelligent}</div>
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
        <span class="nav-icon">◌</span><span>Top Stories</span>
      </button>
      <button class="nav-btn ${state.page === PAGE_MARKETS ? "active" : ""}" onclick="setPage('${PAGE_MARKETS}')">
        <span class="nav-icon">↗</span><span>Markets</span>
      </button>
    </nav>
  `;
}

function sourceRows(story){
  if(Array.isArray(story.sources) && story.sources.length){
    return story.sources.filter(s => s && s.url).slice(0,3);
  }
  if(story.url){
    return [{name: story.source || "Source", url: story.url}];
  }
  return [];
}

function storyCard(story){
  const title = escapeHTML(story.title);
  const summary = escapeHTML(story.summary || "");
  const why = escapeHTML(story.why || "");
  const source = escapeHTML(story.source || "News");
  const cat = escapeHTML(story.cat || "News");
  const time = story.publishedAt ? ageText(story.publishedAt) : "";
  const accent = categoryClass(story.cat);
  const sources = sourceRows(story);
  const sourceCount = Number(story.sourceCount || sources.length || 1);
  const score = Number(story.importanceScore || 0);
  const status = story.status === "Updated" ? "Updated" : "New";
  const verified = story.verified === true;
  const confidence = String(story.confidence || "").toLowerCase();
  const trustLabel = verified ? "✓ Verified" : confidence === "high" ? "High confidence" : "Source-backed";
  const primaryUrl = sources[0]?.url || story.url || "";
  const primaryLink = primaryUrl ? `<a class="source-link" href="${escapeHTML(primaryUrl)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : "";
  const multiSource = sourceCount > 1 ? `<span class="source-count">${sourceCount} sources</span>` : "";
  const importance = score >= 14 ? "Major" : score >= 10 ? "High signal" : "Worth knowing";

  return `
    <article class="card intelligence-card ${accent}">
      <div class="accent-dot"></div>
      <div class="card-top">
        <div class="trust-row"><span class="trust-badge ${verified ? "verified" : ""}">${trustLabel}</span>${multiSource}</div>
        <span class="time">${time}</span>
      </div>
      <h2 class="card-title">${title}</h2>
      ${summary ? `<p class="card-summary">${summary}</p>` : ""}
      ${why ? `<div class="why-line"><span>WHY IT MATTERS</span><p>${why}</p></div>` : ""}
      <div class="card-bottom intelligence-bottom">
        <div class="story-labels"><span class="tag">${cat}</span><span class="signal-tag">${importance}</span><span class="status-tag">${status}</span></div>
        <div class="source-actions"><span class="source-name">${source}</span>${primaryLink}</div>
      </div>
    </article>
  `;
}

function worldFilters(){
  return `
    <div class="filter-strip" aria-label="Filter top stories">
      ${WORLD_FILTERS.map(filter => `
        <button type="button" class="filter-chip ${state.worldFilter === filter ? "active" : ""}" onclick="setWorldFilter('${filter}')">${escapeHTML(filter)}</button>
      `).join("")}
    </div>
  `;
}

function topStoriesView(){
  const news = state.stories
    .filter(story => !["Canadian Markets", "Indian Markets"].includes(story.cat))
    .filter(story => state.worldFilter === "All" || story.cat === state.worldFilter)
    .sort((a,b) => (Number(b.importanceScore || 0) - Number(a.importanceScore || 0)) || (new Date(b.publishedAt) - new Date(a.publishedAt)));

  return `
    <section class="news-section top-stories">
      ${worldFilters()}
      <div class="brief-meta">
        <span>${news.length} ${news.length === 1 ? "event" : "events"}</span>
        <span>Ranked by significance, freshness and source quality</span>
      </div>
      ${news.length ? news.map(storyCard).join("") : `<div class="empty-section">No high-signal ${state.worldFilter === "All" ? "stories" : state.worldFilter + " stories"} right now.</div>`}
    </section>
  `;
}

function sectionBlock(category, icon, label){
  const stories = state.stories
    .filter(story => story.cat === category)
    .sort((a,b) => (Number(b.importanceScore || 0) - Number(a.importanceScore || 0)) || (new Date(b.publishedAt) - new Date(a.publishedAt)));
  return `
    <section class="news-section">
      <div class="section-heading">
        <div class="section-name"><span class="section-icon">${icon}</span><span>${escapeHTML(label)}</span></div>
        <span class="section-count">${stories.length}</span>
      </div>
      ${stories.length ? stories.map(storyCard).join("") : `<div class="empty-section">No high-signal developments right now.</div>`}
    </section>
  `;
}

function setWorldFilter(value){ state.worldFilter = WORLD_FILTERS.includes(value) ? value : "All"; render(); }

function render(){
  let html = header();
  html += `<main class="content">`;

  if(state.page === PAGE_MARKETS){
    html += sectionBlock("Canadian Markets", "CA", "Canadian Markets");
    html += sectionBlock("Indian Markets", "IN", "Indian Markets");
  } else {
    html += topStoriesView();
  }

  if(state.updated){
    const updatedText = new Date(state.updated).toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    const newsFooter = `Updated ${updatedText} · 24-hour rolling window${state.editor ? ` · ${escapeHTML(state.editor)}` : ""}`;
    html += `<div class="fresh">${newsFooter}</div>`;
  }

  html += `</main>${nav()}`;
  document.getElementById("app").innerHTML = html;
}

function setPage(page){
  state.page = page;
  render();
  window.scrollTo({top:0, behavior:"smooth"});
}

async function loadNews(){
  document.getElementById("app").innerHTML = `${header()}<div class="loading"><div class="loading-pulse"></div>Refreshing your brief…</div>${nav()}`;

  try{
    const response = await fetch(`data.json?t=${Date.now()}`, {cache:"no-store"});
    if(!response.ok) throw new Error("Could not load news");
    const data = await response.json();
    const now = Date.now();

    state.updated = data.updated || null;
    state.engine = data.engine || "";
    state.editor = data.editor || "";

    state.stories = (data.stories || [])
      .filter(story => {
        if(!story.publishedAt) return false;
        if(/leave a comment|share this item|share on facebook|whatsapp|see more sharing|submit search|quick search|trending now|read on app|cloudfront|request id:|previous close/i.test(story.summary || "")) return false;
        if(/loafers|fashion|outfit|wardrobe|worth buying|news hour at|watch:|celebrity|bollywood|hollywood|viral video/i.test(story.title || "")) return false;
        const age = now - new Date(story.publishedAt).getTime();
        return age >= 0 && age <= MAX_AGE_MS;
      })
      .sort((a,b) => (Number(b.importanceScore || 0) - Number(a.importanceScore || 0)) || (new Date(b.publishedAt) - new Date(a.publishedAt)));

    render();
  }catch(error){
    console.error(error);
    document.getElementById("app").innerHTML = `${header()}<div class="empty"><strong>Couldn’t refresh Briefly.</strong><br><br>Check your connection and try again.<br><br><button class="refresh" onclick="loadNews()">↻ Try again</button></div>${nav()}`;
  }
}

loadNews();
