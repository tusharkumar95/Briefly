const MAX_AGE_MS = 6 * 60 * 60 * 1000;

let state = {
  stories: [],
  category: "All",
  updated: null
};

const categories = [
  ["All", "✨"],
  ["India", "🇮🇳"],
  ["Canada", "🇨🇦"],
  ["Indian Markets", "📈"],
  ["Canadian Markets", "📈"],
  ["AI", "🤖"]
];

function escapeHTML(value){
  return String(value ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function ageText(date){
  const ms = Date.now() - new Date(date).getTime();

  if(ms < 60 * 1000) return "now";

  const minutes = Math.floor(ms / 60000);

  if(minutes < 60){
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

function header(title="Today", subtitle="Your world, filtered."){
  return `
    <header class="top">
      <div class="eyebrow">
        <span>YOUR PERSONAL BRIEF</span>
        <button class="refresh" onclick="loadNews()">↻ Refresh</button>
      </div>

      <div class="title">${escapeHTML(title)}</div>
      <div class="subtitle">${escapeHTML(subtitle)}</div>
    </header>
  `;
}

function nav(){
  return `
    <nav class="bottom-nav">
      ${categories.map(([name,icon]) => `
        <button
          class="nav-btn ${state.category===name ? "active" : ""}"
          onclick="setCategory('${name}')"
        >
          <div>${icon}</div>
          <div>${name === "Indian Markets" ? "India Mkts" :
                 name === "Canadian Markets" ? "Canada Mkts" :
                 name}</div>
        </button>
      `).join("")}
    </nav>
  `;
}

function storyCard(story){
  const title = escapeHTML(story.title);
  const summary = escapeHTML(story.summary || "");
  const source = escapeHTML(story.source || "News");
  const cat = escapeHTML(story.cat || "");
  const time = story.publishedAt ? ageText(story.publishedAt) : "";

  return `
    <article class="card" onclick="openStory('${encodeURIComponent(story.url || "")}')">
      <div class="card-top">
        <span class="source">${source}</span>
        <span class="time">${time}</span>
      </div>

      <h2 class="card-title">${title}</h2>

      ${summary ? `
        <p class="card-summary">${summary}</p>
      ` : ""}

      <div class="card-bottom">
        <span class="tag">${cat}</span>
        <span class="read">Read →</span>
      </div>
    </article>
  `;
}

function render(){
  const visible = state.category === "All"
    ? state.stories
    : state.stories.filter(s => s.cat === state.category);

  let html = header(
    state.category === "All" ? "Today" : state.category,
    "Only the news that matters to you."
  );

  html += `<main class="content">`;

  if(!visible.length){
    html += `
      <div class="empty">
        No fresh stories in this category right now.
        <br><br>
        Briefly only keeps news from the last 6 hours.
      </div>
    `;
  }else{
    html += visible.map(storyCard).join("");
  }

  if(state.updated){
    const updatedText = new Date(state.updated).toLocaleTimeString([], {
      hour:"numeric",
      minute:"2-digit"
    });

    html += `
      <div class="fresh">
        Feed updated ${updatedText} · Stories older than 6 hours are automatically removed.
      </div>
    `;
  }

  html += `</main>`;
  html += nav();

  document.getElementById("app").innerHTML = html;
}

function setCategory(category){
  state.category = category;
  render();
  window.scrollTo({top:0,behavior:"smooth"});
}

function openStory(encoded){
  const url = decodeURIComponent(encoded);

  if(url){
    window.open(url,"_blank","noopener,noreferrer");
  }
}

async function loadNews(){
  document.getElementById("app").innerHTML = `
    ${header("Briefly","Refreshing your personal news feed…")}
    <div class="loading">Getting the latest stories…</div>
    ${nav()}
  `;

  try{
    const response = await fetch(`data.json?t=${Date.now()}`, {
      cache:"no-store"
    });

    if(!response.ok){
      throw new Error("Could not load news");
    }

    const data = await response.json();

    const now = Date.now();

    state.updated = data.updated || null;

    state.stories = (data.stories || [])
      .filter(story => {
        if(!story.publishedAt) return true;

        const age = now - new Date(story.publishedAt).getTime();

        return age >= 0 && age <= MAX_AGE_MS;
      })
      .sort((a,b) => {
        return new Date(b.publishedAt || 0) -
               new Date(a.publishedAt || 0);
      });

    render();

  }catch(error){
    console.error(error);

    document.getElementById("app").innerHTML = `
      ${header("Briefly","Unable to refresh right now.")}
      <div class="empty">
        Please check your internet connection and try again.
        <br><br>
        <button class="refresh" onclick="loadNews()">↻ Try again</button>
      </div>
      ${nav()}
    `;
  }
}

loadNews();
