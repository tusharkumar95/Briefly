import json
import re

MARKET_SERVICE = re.compile(
    r"(?i)\b("
    r"bonus issue|stock split|dividend alert|record date|ex-dividend|last day to buy|do you own any|"
    r"stocks? to buy today|top stocks? to buy|multibagger|price target|brokerage picks?|buy call|sell call|"
    r"ipo opens? for subscription|ipo subscription|gmp at|grey market premium|should you bid|bid or skip|"
    r"should you apply|ipo allotment|ipo listing|subscription status"
    r")\b"
)

COMMENTARY_ONLY = re.compile(
    r"(?i)\b(pushes back on .*warnings?|doomsday warnings?|doomer narrative|shares? his views?|"
    r"weighs in on|reacts? to .* debate|says critics are wrong|what .* thinks about)\b"
)

PAGE_JUNK = re.compile(
    r"(?i)(share price|daily newspaper is available online|read today[’']s paper|stock analysis|"
    r"market statistics|previous close|52 week high|52 week low|volume traded|buying range|"
    r"target price|stop loss|subscribe now|sign in to read)"
)

SCIENCE_HEALTH = re.compile(
    r"(?i)\b(retina|retinal|implant|disease|patient|therapy|treatment|medical|medicine|clinical|"
    r"vision-restoring|vision restoring|biotech|health|drug|vaccine|gene therapy|neurotechnology|prosthetic)\b"
)

AI_SIGNAL = re.compile(
    r"(?i)\b(ai|artificial intelligence|machine learning|language model|llm|chatbot|agent|inference|"
    r"training model|openai|anthropic|deepmind|nvidia|cerebras|gpu|foundation model|robotics)\b"
)


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_repeated_title(title, summary):
    title = normalize(title)
    summary = normalize(summary)
    if not title or not summary:
        return summary

    # Exact headline accidentally copied at the beginning of an extract.
    if summary.lower().startswith(title.lower()):
        summary = summary[len(title):].lstrip(" :-–—|.")

    # Headline punctuation sometimes differs slightly. Compare normalized word prefixes.
    title_words = re.findall(r"[a-z0-9]+", title.lower())
    summary_words = list(re.finditer(r"[a-z0-9]+", summary.lower()))
    if len(title_words) >= 5 and len(summary_words) >= len(title_words):
        prefix_words = [match.group(0) for match in summary_words[:len(title_words)]]
        overlap = sum(a == b for a, b in zip(title_words, prefix_words)) / len(title_words)
        if overlap >= 0.82:
            end = summary_words[len(title_words) - 1].end()
            summary = summary[end:].lstrip(" :-–—|.")

    return normalize(summary)


def improve_why(story):
    title = normalize(story.get("title", ""))
    summary = normalize(story.get("summary", ""))
    combined = title + " " + summary[:300]

    if SCIENCE_HEALTH.search(combined) and not AI_SIGNAL.search(combined):
        return "This matters because it could expand treatment options or demonstrate a clinically meaningful new medical technology."
    if re.search(r"(?i)\b(rbi|forex|fx speculation|currency market|rupee)\b", combined):
        return "RBI action on currency speculation can affect rupee volatility, hedging costs and foreign-exchange conditions for businesses and investors."
    if re.search(r"(?i)\b(bank of america|money laundering|regulatory penalty|fine)\b", combined):
        return "A penalty of this scale can increase regulatory scrutiny and compliance costs for a major global financial institution."
    if re.search(r"(?i)\b(imf|global growth|world growth)\b", combined):
        return "Changes in the global growth outlook can influence markets, trade, borrowing conditions and business investment across countries."
    if re.search(r"(?i)\b(trade deal|tariff|market access)\b", combined):
        return "The outcome could change tariffs, market access and trade conditions for businesses in both countries."
    return normalize(story.get("why", ""))


def main():
    with open("data.json", encoding="utf-8") as handle:
        data = json.load(handle)

    kept = []
    rejected = []
    for raw in data.get("stories", []):
        story = dict(raw)
        title = normalize(story.get("title", ""))
        summary = strip_repeated_title(title, story.get("summary", ""))
        combined = title + " " + summary[:280]

        if MARKET_SERVICE.search(combined):
            rejected.append((title, "market-service content"))
            continue
        if COMMENTARY_ONLY.search(combined):
            rejected.append((title, "commentary-only content"))
            continue
        if PAGE_JUNK.search(summary):
            rejected.append((title, "page boilerplate"))
            continue
        if len(summary) < 80:
            rejected.append((title, "summary too thin after cleanup"))
            continue

        story["summary"] = summary

        # Some technology feeds carry biotech/neurotech stories. Keep useful science,
        # but do not label it AI unless AI is actually material to the event.
        if story.get("cat") == "AI" and SCIENCE_HEALTH.search(combined) and not AI_SIGNAL.search(combined):
            story["cat"] = "World"
            story["icon"] = "🌍"
            story["categories"] = ["World"]

        story["why"] = improve_why(story)
        kept.append(story)

    if not kept:
        raise RuntimeError("Final editorial cleanup rejected every story")

    kept.sort(key=lambda item: (float(item.get("importanceScore", 0)), item.get("publishedAt", "")), reverse=True)
    data["stories"] = kept[:10]
    data["finalRejectedCount"] = len(rejected)

    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    print("Final editorial gate kept", len(data["stories"]), "stories and rejected", len(rejected))
    for title, reason in rejected:
        print("Rejected:", reason, "—", title)


if __name__ == "__main__":
    main()
