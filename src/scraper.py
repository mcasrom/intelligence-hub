import feedparser
import requests
from datetime import datetime
from src.rotation import RateLimiter, FeedCache


COUNTRIES = {
    "elpais.com": "espana", "elmundo.es": "espana",
    "lavanguardia.com": "espana", "eldiariocantabria.publico.es": "espana",
    "washingtonpost.com": "estados_unidos", "wsj.com": "estados_unidos",
    "lemonde.fr": "francia", "lefigaro.fr": "francia",
    "bbc.co.uk": "reino_unido", "theguardian.com": "reino_unido",
    "corriere.it": "italia", "ilsole24ore.com": "italia",
    "spiegel.de": "alemania", "dw.com": "alemania",
    "folha.uol.com.br": "brasil", "oglobo.globo.com": "brasil",
}


def detect_country(url):
    for domain, country in COUNTRIES.items():
        if domain in url:
            return country
    return "internacional"


def process_feed(source_name, source_url, lang, timeout=15):
    status = {"name": source_name, "url": source_url, "lang": lang, "ok": False, "articles": 0, "error": None}
    try:
        headers = {
            "User-Agent": "daily_news/1.0 (+https://github.com/mcasrom/daily_readings)"
        }
        resp = requests.get(source_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except requests.Timeout:
        status["error"] = f"timeout (> {timeout}s)"
        print(f"  [TIMEOUT] {source_name} (> {timeout}s)")
        return [], status
    except Exception as e:
        status["error"] = str(e)[:60]
        print(f"  [ERROR] {source_name}: {e}")
        return [], status

    articles = []
    for entry in feed.entries[:10]:
        article = {
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "source": source_name,
            "country": detect_country(entry.get("link", "")),
            "lang": lang,
            "published": entry.get("published", datetime.utcnow().isoformat()),
        }
        if article["title"] and article["url"]:
            articles.append(article)

    status["ok"] = True
    status["articles"] = len(articles)
    print(f"  [OK] {source_name}: {len(articles)} artículos")
    return articles, status


def scrape_all(sources, rate_limiter, feed_cache, max_feeds=None):
    all_articles = []
    all_status = []
    processed = 0
    for country, feeds in sources.items():
        print(f"\n[{country}]")
        for feed_cfg in feeds:
            if max_feeds and processed >= max_feeds:
                return all_articles, all_status
            processed += 1
            name = feed_cfg["name"]
            url = feed_cfg["url"]
            lang = feed_cfg["lang"]

            cached = feed_cache.get(url)
            if cached:
                print(f"  [CACHE] {name}: {len(cached)} artículos")
                all_articles.extend(cached)
                all_status.append({"name": name, "url": url, "lang": lang, "ok": True, "articles": len(cached), "error": None, "cached": True})
                continue

            rate_limiter.wait_if_needed(url)
            articles, status = process_feed(name, url, lang)
            all_status.append(status)

            if articles:
                feed_cache.set(url, articles)
                all_articles.extend(articles)

    return all_articles, all_status
