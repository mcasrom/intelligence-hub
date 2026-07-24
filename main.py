import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone

from src.db import init_db, save_articles, get_articles_window, save_word_frequencies, save_sync_event, update_clusters, get_sync_events, get_words_in_window
from src.scraper import scrape_all
from src.rotation import RateLimiter, FeedCache
from src.embeddings import EmbeddingsProvider
from src.clusterer import compute_clusters
from src.sync_detector import detect_sync_groups
from src.analytics import compute_frequencies, compute_trending
from src.llm import LLMProvider
from src.generator import generate_briefing, generate_clusters_page, generate_json_data
from src.deploy import deploy


def load_config():
    config_path = Path(__file__).parent / "config.yml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def main(fast=False):
    now = datetime.now(timezone.utc)
    print("=" * 60)
    print("daily_news — Inteligencia Geopolítica")
    print("=" * 60)

    config = load_config()
    mode = config.get("mode", "test")
    print(f"\n[*] Modo: {mode.upper()}")
    print(f"[*] Fecha: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    date_str = now.strftime("%y%m%d")

    # Init DB
    print("\n[*] Inicializando base de datos...")
    init_db()

    # Rate limiting + cache
    rate_limiter = RateLimiter(config.get("rotation", {}))
    feed_cache = FeedCache(ttl=config.get("rotation", {}).get("cache_ttl", 1800))

    # 1. SCRAPING
    print("\n" + "=" * 60)
    print("FASE 1: Scraping RSS")
    print("=" * 60)
    articles = scrape_all(config["sources"], rate_limiter, feed_cache,
                          max_feeds=3 if fast else None)
    all_articles = articles[0] if isinstance(articles, tuple) else articles
    feed_status = articles[1] if isinstance(articles, tuple) else []
    print(f"\n[*] Total artículos recolectados: {len(all_articles)}")

    if not all_articles:
        print("[!] No hay artículos, abortando")
        return

    # 2. STORE
    print("\n" + "=" * 60)
    print("FASE 2: Almacenando en BD")
    print("=" * 60)
    saved = save_articles(all_articles)
    print(f"[*] Artículos nuevos guardados: {saved}")

    db_articles = get_articles_window(config.get("clustering", {}).get("window_days", 7))
    print(f"[*] Artículos en ventana: {len(db_articles)}")

    if len(db_articles) < 2:
        print("[!] Muy pocos artículos para analizar")
        generate_briefing(db_articles, [], [], {}, {}, date_str, sources=config["sources"],
                          feed_status=feed_status)
        generate_json_data(db_articles, [], [], {}, {}, date_str)
        deploy(mode, config.get("deploy", {}))
        return

    # 3. EMBEDDINGS
    print("\n" + "=" * 60)
    print("FASE 3: Generando embeddings")
    print("=" * 60)
    embedder = EmbeddingsProvider(mode)
    titles = [a["title"] for a in db_articles]

    print(f"[*] Generando {len(titles)} embeddings...")
    try:
        embeddings = embedder.embed(titles)
        print(f"[OK] {len(embeddings)} embeddings generados")
    except Exception as e:
        print(f"[ERROR] Embeddings fallaron: {e}")
        generate_briefing(db_articles, [], [], {}, {}, date_str)
        generate_json_data(db_articles, [], [], {}, {}, date_str)
        deploy(mode, config.get("deploy", {}))
        return

    # 4. CLUSTERING
    print("\n" + "=" * 60)
    print("FASE 4: Clustering + Sincronizadas")
    print("=" * 60)
    clustering_cfg = config.get("clustering", {})
    clustered, clusters = compute_clusters(
        db_articles, embeddings,
        min_cluster_size=clustering_cfg.get("min_cluster_size", 2),
        min_samples=clustering_cfg.get("min_samples", 1),
    )
    update_clusters(clustered)

    active_clusters = {k: v for k, v in clusters.items() if v["size"] >= 2}
    print(f"[*] Clústeres encontrados: {len(active_clusters)}")

    # 5. SYNC DETECTION
    sync_events = detect_sync_groups(
        db_articles, embeddings,
        threshold=clustering_cfg.get("similarity_threshold", 0.75)
    )
    print(f"[*] Eventos sincronizados: {len(sync_events)}")

    for se in sync_events:
        save_sync_event(se["topic"], se["article_ids"], se["sources"], int(se.get("is_editorial", False)))
    saved_syncs = get_sync_events()
    editorials = [s for s in saved_syncs if s["is_editorial"]]
    print(f"[*] Editoriales sincronizados: {len(editorials)}")

    # 6. ANALYTICS
    print("\n" + "=" * 60)
    print("FASE 5: Analítica de palabras")
    print("=" * 60)
    windows = config.get("analytics", {}).get("word_windows", [3, 5, 7])
    frequencies = compute_frequencies(db_articles, windows)

    for days in windows:
        word_count = sum(len(v) for v in frequencies[days].values())
        print(f"  [{days}d] {word_count} palabras clave")

    trends = compute_trending(frequencies)
    if trends:
        for lang, words in trends.items():
            top = list(words.keys())[:5]
            print(f"  [TRENDING {lang}] {', '.join(top)}")

    # 7. LLM ENRICHMENT (timeboxed - no rompe el pipeline si falla)
    print("\n" + "=" * 60)
    print("FASE 6: Enriquecimiento LLM")
    print("=" * 60)
    llm = LLMProvider(mode)
    enriched_clusters = {}
    for cid, cdata in list(active_clusters.items())[:5]:
        titles_list = [a["title"] for a in cdata["articles"]]
        try:
            summary = llm.label_cluster(titles_list)
            detailed = llm.summarize_cluster(titles_list)
            cdata["summary"] = summary
            cdata["detailed"] = detailed
            enriched_clusters[cid] = cdata
            print(f"  [OK] Cluster {cid}: {str(summary)[:60]}...")
        except Exception as e:
            print(f"  [WARN] Cluster {cid}: LLM falló ({e})")
            enriched_clusters[cid] = cdata

    # 8. GENERATION
    print("\n" + "=" * 60)
    print("FASE 7: Generando HTML + JSON")
    print("=" * 60)
    llm_cfg = config.get("llm", {}).get("test" if mode == "test" else "production", {})
    llm_model = llm_cfg.get("ollama_model") or llm_cfg.get("groq_model")
    generate_briefing(db_articles, enriched_clusters, sync_events, frequencies, trends,
                      date_str, sources=config["sources"], llm_model=llm_model,
                      wordclouds={}, breaking=[], entities={},
                      feed_status=feed_status,
                      site_domain=config.get("deploy", {}).get("site_domain"))
    generate_clusters_page(enriched_clusters, date_str)
    generate_json_data(db_articles, enriched_clusters, sync_events, frequencies, trends, date_str)

    # 9. DEPLOY
    print("\n" + "=" * 60)
    print("FASE 8: Deploy")
    print("=" * 60)
    deploy(mode, config.get("deploy", {}))

    print("\n" + "=" * 60)
    print("[OK] Proceso completado")
    print("=" * 60)


if __name__ == "__main__":
    fast = "--fast" in sys.argv
    main(fast=fast)
