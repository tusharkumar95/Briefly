(() => {
  state.marketIntel = null;
  state.marketIntelError = "";

  if (pageConfig?.[PAGE_MARKETS]) {
    pageConfig[PAGE_MARKETS].subtitle = "What moved Canada and India — direction, drivers and the evidence behind it.";
  }

  function pctText(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `${n >= 0 ? "+" : ""}${n.toFixed(2)}%` : "Move unavailable";
  }

  function indexPrice(index, market) {
    const n = Number(index?.price);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString(market === "India" ? "en-IN" : "en-CA", { maximumFractionDigits: 2 });
  }

  function directionLabel(direction) {
    if (direction === "up") return "▲ Higher";
    if (direction === "down") return "▼ Lower";
    if (direction === "flat") return "— Flat";
    if (direction === "mixed") return "↔ Mixed";
    return "? Unclear";
  }

  function directionClass(direction) {
    return ["up", "down", "flat", "mixed"].includes(direction) ? direction : "unclear";
  }

  function sourceLinks(market) {
    const rows = Array.isArray(market?.sources) ? market.sources.slice(0, 4) : [];
    if (!rows.length) return '<span class="market-no-source">No driver sources available</span>';
    return rows.map(row => `<a href="${escapeHTML(row.url || "")}" target="_blank" rel="noopener noreferrer">${escapeHTML(row.name || "Source")} ↗</a>`).join("");
  }

  function driverRows(market) {
    const rows = Array.isArray(market?.drivers) ? market.drivers : [];
    if (!rows.length) return '<div class="market-empty-driver">No verified driver was established.</div>';
    return rows.slice(0, 4).map(row => `
      <div class="market-driver ${row.kind === "driver" ? "causal" : "context"}">
        <div class="market-driver-kicker">${row.kind === "driver" ? "DRIVER" : "CONTEXT"}</div>
        <strong>${escapeHTML(row.label || "Market factor")}</strong>
        <p>${escapeHTML(row.detail || "")}</p>
      </div>`).join("");
  }

  function indexStrip(market) {
    const primary = market?.primaryIndex || {};
    const secondary = market?.secondaryIndex;
    const primaryMove = Number(primary.changePct);
    const primaryDirection = Number.isFinite(primaryMove) ? (primaryMove > 0.12 ? "up" : primaryMove < -0.12 ? "down" : "flat") : market?.direction;
    const secondaryHtml = secondary ? `
      <div class="market-index secondary">
        <small>${escapeHTML(secondary.name || secondary.symbol || "Secondary index")}</small>
        <strong>${indexPrice(secondary, market.label)}</strong>
        <span class="${directionClass(Number(secondary.changePct) > 0.12 ? "up" : Number(secondary.changePct) < -0.12 ? "down" : "flat")}">${pctText(secondary.changePct)}</span>
      </div>` : "";
    return `
      <div class="market-index-strip">
        <div class="market-index primary">
          <small>${escapeHTML(primary.name || primary.symbol || "Index")}</small>
          <strong>${indexPrice(primary, market.label)}</strong>
          <span class="${directionClass(primaryDirection)}">${pctText(primary.changePct)}</span>
        </div>
        ${secondaryHtml}
      </div>`;
  }

  function relatedStories(label) {
    const categories = label === "Canada" ? ["Canadian Markets", "Canada"] : ["Indian Markets", "India"];
    return state.stories
      .filter(story => categories.includes(story.cat))
      .sort((a,b) => (Number(b.importanceScore || 0) - Number(a.importanceScore || 0)) || String(b.publishedAt || "").localeCompare(String(a.publishedAt || "")))
      .slice(0, 2);
  }

  function marketCard(market) {
    if (!market) return "";
    const related = relatedStories(market.label);
    const confidence = String(market.confidence || "low").toUpperCase();
    return `
      <section class="market-intel-card ${directionClass(market.direction)}">
        <div class="market-intel-head">
          <div>
            <span class="market-country">${market.label === "Canada" ? "🇨🇦" : "🇮🇳"} ${escapeHTML(market.label)}</span>
            <h2>${escapeHTML(market.headline || "Market update")}</h2>
          </div>
          <div class="market-direction ${directionClass(market.direction)}">
            <strong>${directionLabel(market.direction)}</strong>
            <span>${escapeHTML(market.move || "")}</span>
          </div>
        </div>
        ${indexStrip(market)}
        <div class="market-why">
          <div class="market-section-label">WHY IT MOVED</div>
          <p>${escapeHTML(market.why || "No verified causal explanation is available yet.")}</p>
        </div>
        <div class="market-driver-grid">${driverRows(market)}</div>
        ${Array.isArray(market.sectors) && market.sectors.length ? `<div class="market-sectors"><span>IN PLAY</span>${market.sectors.map(value => `<b>${escapeHTML(value)}</b>`).join("")}</div>` : ""}
        <div class="market-evidence">
          <span>${confidence} CONFIDENCE · ${Number(market.evidenceCount || 0)} SOURCE${Number(market.evidenceCount || 0) === 1 ? "" : "S"}</span>
          <div>${sourceLinks(market)}</div>
        </div>
        ${related.length ? `<div class="market-related"><div class="market-section-label">RELATED BRIEFLY EVENTS</div>${related.map(storyCard).join("")}</div>` : ""}
      </section>`;
  }

  function marketsViewV2() {
    const data = state.marketIntel;
    if (!data?.markets) {
      return `${sectionBlock("Canadian Markets", "CA", "Canadian Markets")}${sectionBlock("Indian Markets", "IN", "Indian Markets")}`;
    }
    return `
      <section class="markets-v2">
        <div class="market-policy"><strong>Cause, not commentary.</strong><span>Index direction comes from market data. A factor is labelled DRIVER only when the collected sources connect it to the move; otherwise it stays CONTEXT.</span></div>
        ${marketCard(data.markets.Canada)}
        ${marketCard(data.markets.India)}
      </section>`;
  }

  const baseRender = render;
  render = function() {
    if (state.page !== PAGE_MARKETS || !state.marketIntel?.markets) {
      return baseRender();
    }
    let html = header();
    html += `<main class="content">${marketsViewV2()}</main>${nav()}`;
    document.getElementById("app").innerHTML = html;
  };

  async function refreshMarketIntel() {
    try {
      const response = await fetch(`market-intelligence.json?t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Market intelligence unavailable");
      const data = await response.json();
      if (data?.engine !== "Briefly Markets Intelligence v1" || !data?.markets) throw new Error("Unexpected market feed");
      state.marketIntel = data;
      state.marketIntelError = "";
      if (state.page === PAGE_MARKETS) render();
    } catch (error) {
      state.marketIntelError = String(error?.message || error);
    }
  }

  const priorLoad = loadNews;
  loadNews = async function() {
    await priorLoad();
    await refreshMarketIntel();
  };

  refreshMarketIntel();
})();
