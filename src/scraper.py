import feedparser
import requests
import time
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.rotation import RateLimiter, FeedCache
from src.db import update_feed_health


COUNTRIES = {
    "elpais.com": "espana", "elmundo.es": "espana",
    "lavanguardia.com": "espana", "eldiariocantabria.publico.es": "espana",
    "washingtonpost.com": "estados_unidos", "wsj.com": "estados_unidos",
    "cnn.com": "estados_unidos", "nytimes.com": "estados_unidos",
    "lemonde.fr": "francia", "lefigaro.fr": "francia",
    "bbc.co.uk": "reino_unido", "theguardian.com": "reino_unido",
    "corriere.it": "italia", "ilsole24ore.com": "italia",
    "spiegel.de": "alemania", "dw.com": "alemania",
    "folha.uol.com.br": "brasil", "oglobo.globo.com": "brasil",
    "g1.globo.com": "brasil",
    "lanacion.com.ar": "argentina", "elcohetealaluna.com": "argentina",
    "aljazeera.com": "qatar", "thenationalnews.com": "emiratos_arabes",
    "aa.com.tr": "turquia", "al-monitor.com": "internacional",
}


def detect_country(url):
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
    except Exception:
        return "internacional"
    for domain, country in COUNTRIES.items():
        if netloc == domain or netloc.endswith("." + domain):
            return country
    return "internacional"


def _parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime(*t[:6]).isoformat()
            except Exception:
                pass
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            reparsed = feedparser.parse(raw).entries[0].get("published_parsed")
            if reparsed:
                return datetime(*reparsed[:6]).isoformat()
        except Exception:
            pass
    return datetime.utcnow().isoformat()


def _extract_summary(entry, max_chars=400):
    summary = ""
    for key in ("summary", "description"):
        if entry.get(key):
            summary = entry[key]
            break
    if not summary and entry.get("content"):
        try:
            summary = entry["content"][0].get("value", "")
        except Exception:
            pass
    if summary:
        try:
            import html
            summary = html.unescape(summary)
        except Exception:
            pass
        import re
        summary = re.sub(r"<[^>]+>", " ", summary)
        summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:max_chars]


def process_feed(source_name, source_url, lang, timeout=15, rate_limiter=None):
    status = {"name": source_name, "url": source_url, "lang": lang, "ok": False, "articles": 0, "error": None}
    headers = {
        "User-Agent": "daily_news/1.0 (+https://github.com/mcasrom/daily_readings)"
    }
    last_error = None
    for attempt in range(1, (rate_limiter.max_retries + 2) if rate_limiter else 2):
        try:
            resp = requests.get(source_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            break
        except requests.Timeout:
            last_error = f"timeout (> {timeout}s)"
            status_code = None
        except requests.HTTPError as e:
            last_error = str(e)[:120]
            status_code = e.response.status_code if e.response is not None else None
        except Exception as e:
            last_error = str(e)[:120]
            status_code = None

        if rate_limiter and rate_limiter.should_retry(attempt, status_code):
            delay = rate_limiter.get_backoff(attempt)
            print(f"  [RETRY] {source_name} ({last_error}), reintento {attempt} en {delay:.1f}s")
            time.sleep(delay)
            continue

        error_msg = last_error
        status["error"] = error_msg
        print(f"  [ERROR] {source_name}: {error_msg}")
        update_feed_health(source_name, source_url, False, error_msg)
        return [], status
    else:
        error_msg = last_error
        status["error"] = error_msg
        print(f"  [ERROR] {source_name}: {error_msg}")
        update_feed_health(source_name, source_url, False, error_msg)
        return [], status

    articles = []
    for entry in feed.entries[:20]:
        article = {
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "source": source_name,
            "country": detect_country(entry.get("link", "")),
            "lang": lang,
            "published": _parse_date(entry),
            "summary": _extract_summary(entry),
        }
        if article["title"] and article["url"]:
            articles.append(article)

    status["ok"] = True
    status["articles"] = len(articles)
    print(f"  [OK] {source_name}: {len(articles)} artículos")
    update_feed_health(source_name, source_url, True)
    return articles, status


def _process_feed_wrapper(feed_cfg, country, rate_limiter, feed_cache):
    name = feed_cfg["name"]
    url = feed_cfg["url"]
    lang = feed_cfg["lang"]

    cached = feed_cache.get(url)
    if cached:
        print(f"  [CACHE] {name}: {len(cached)} artículos")
        return cached, {"name": name, "url": url, "lang": lang, "ok": True, "articles": len(cached), "error": None, "cached": True}

    rate_limiter.wait_if_needed(url)
    articles, status = process_feed(name, url, lang, rate_limiter=rate_limiter)

    if articles:
        feed_cache.set(url, articles)
    return articles, status


def scrape_all(sources, rate_limiter, feed_cache, max_feeds=None):
    all_articles = []
    all_status = []

    tasks = []
    processed = 0
    for country, feeds in sources.items():
        for feed_cfg in feeds:
            if max_feeds and processed >= max_feeds:
                break
            processed += 1
            tasks.append((country, feed_cfg))

    if max_feeds:
        tasks = tasks[:max_feeds]

    print(f"  [PARALLEL] Scrapeando {len(tasks)} feeds con ThreadPoolExecutor...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for country, feed_cfg in tasks:
            f = executor.submit(_process_feed_wrapper, feed_cfg, country, rate_limiter, feed_cache)
            futures[f] = (country, feed_cfg["name"])

        for f in as_completed(futures):
            country, name = futures[f]
            try:
                articles, status = f.result()
                all_status.append(status)
                if articles:
                    all_articles.extend(articles)
            except Exception as e:
                print(f"  [ERROR] {name}: {e}")
                all_status.append({"name": name, "url": "", "lang": "?", "ok": False, "articles": 0, "error": str(e)[:120]})

    print(f"\n[*] Total feeds procesados: {len(all_status)}")
    return all_articles, all_status
