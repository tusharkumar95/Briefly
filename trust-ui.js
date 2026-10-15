(() => {
  if (typeof storyCard !== "function") return;
  const renderBaseStoryCard = storyCard;

  storyCard = function(story) {
    let html = renderBaseStoryCard(story);
    if (story?.verified !== true) return html;

    const sourceCount = Math.max(1, Number(story?.sourceCount || story?.sources?.length || 1));
    const sourceQuality = String(story?.sourceQuality || "general").toLowerCase();
    const corroborated = sourceCount > 1 || sourceQuality === "primary" || sourceQuality === "tier-1";
    const label = corroborated ? "✓ Corroborated" : "✓ Evidence checked";

    html = html.replace("✓ Verified", label);
    return html;
  };
})();
