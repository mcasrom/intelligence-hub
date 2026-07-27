import os
import sys
import yaml
import json
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.db import init_db, save_articles, get_articles_window, save_word_frequencies, save_sync_event, update_clusters, get_sync_events, get_words_in_window, rotate_articles
from src.scraper import scrape_all
from src.rotation import RateLimiter, FeedCache
from src.embeddings import EmbeddingsProvider
from src.clusterer import compute_clusters
from src.sync_detector import detect_sync_groups
from src.analytics import compute_frequencies, compute_trending
from src.llm import LLMProvider
from src.narrative import detect_actor_mentions, aggregate_stance, detect_coordination
from src.generator import generate_briefing, generate_clusters_page, generate_json_data
from src.deploy import deploy


TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def notify_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage',
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception:
        pass


def load_config():
    config_path = Path(__file__).parent / 'config.yml'
    with open(config_path) as f:
        return yaml.safe_load(f)


def main(fast=False):
    now = datetime.now(timezone.utc)
    print('=' * 60)
    print('daily_news - Inteligencia Geopolitica')
    print('=' * 60)

    config = load_config()
    mode = config.get('mode', 'test')
    print('')
    print('[*] Modo: ' + mode.upper())
    print('[*] Fecha: ' + now.strftime('%Y-%m-%d %H:%M:%S'))

    date_str = now.strftime('%y%m%d')

    print('')
    print('[*] Inicializando base de datos...')
    init_db()

    print('')
    print('[*] Rotacion: eliminando articulos > 7 dias...')
    try:
        del_arts, del_words, del_syncs = rotate_articles(days=config.get('clustering', {}).get('window_days', 7))
        print('    Eliminados: ' + str(del_arts) + ' articulos, ' + str(del_words) + ' palabras, ' + str(del_syncs) + ' sync_events')
    except Exception as e:
        print('    [WARN] Rotation fallo: ' + str(e))

    rate_limiter = RateLimiter(config.get('rotation', {}))
    feed_cache = FeedCache(ttl=config.get('rotation', {}).get('cache_ttl', 1800))

    errors = []

    print('')
    print('=' * 60)
    print('FASE 1: Scraping RSS')
    print('=' * 60)
    try:
        articles = scrape_all(config['sources'], rate_limiter, feed_cache,
                              max_feeds=3 if fast else None)
        all_articles = articles[0] if isinstance(articles, tuple) else articles
        feed_status = articles[1] if isinstance(articles, tuple) else []
        print('')
        print('[*] Total articulos recolectados: ' + str(len(all_articles)))
    except Exception as e:
        print('[ERROR] Scraping fallo: ' + str(e))
        errors.append('Scraping: ' + str(e))
        notify_telegram('<b>daily_news FALLA</b>\nScraping: ' + str(e))
        return

    if not all_articles:
        print('[!] No hay articulos, abortando')
        notify_telegram('daily_news: 0 articulos recolectados')
        return

    print('')
    print('=' * 60)
    print('FASE 2: Almacenando en BD')
    print('=' * 60)
    saved = save_articles(all_articles)
    print('[*] Articulos nuevos guardados: ' + str(saved))

    db_articles = get_articles_window(config.get('clustering', {}).get('window_days', 7))
    print('[*] Articulos en ventana: ' + str(len(db_articles)))

    if len(db_articles) < 2:
        print('[!] Muy pocos articulos para analizar')
        generate_briefing(db_articles, {}, [], {}, {}, date_str, sources=config['sources'],
                          feed_status=feed_status)
        generate_json_data(db_articles, {}, [], {}, {}, date_str)
        deploy(mode, config.get('deploy', {}))
        return

    print('')
    print('=' * 60)
    print('FASE 3: Generando embeddings')
    print('=' * 60)
    embedder = EmbeddingsProvider(mode)
    titles = [a['title'] for a in db_articles]

    print('[*] Generando ' + str(len(titles)) + ' embeddings...')
    try:
        embeddings = embedder.embed(titles)
        print('[OK] ' + str(len(embeddings)) + ' embeddings generados')
    except Exception as e:
        print('[ERROR] Embeddings fallaron: ' + str(e))
        errors.append('Embeddings: ' + str(e))
        generate_briefing(db_articles, {}, [], {}, {}, date_str)
        generate_json_data(db_articles, {}, [], {}, {}, date_str)
        deploy(mode, config.get('deploy', {}))
        return

    print('')
    print('=' * 60)
    print('FASE 4: Clustering + Sincronizadas')
    print('=' * 60)
    clustering_cfg = config.get('clustering', {})
    clustered, clusters = compute_clusters(
        db_articles, embeddings,
        min_cluster_size=clustering_cfg.get('min_cluster_size', 2),
        min_samples=clustering_cfg.get('min_samples', 1),
    )
    update_clusters(clustered)

    active_clusters = {k: v for k, v in clusters.items() if v['size'] >= 2}
    print('[*] Clusters encontrados: ' + str(len(active_clusters)))

    sync_events = detect_sync_groups(
        db_articles, embeddings,
        threshold=clustering_cfg.get('similarity_threshold', 0.75)
    )
    print('[*] Eventos sincronizados: ' + str(len(sync_events)))

    for se in sync_events:
        save_sync_event(se['topic'], se['article_ids'], se['sources'], int(se.get('is_editorial', False)))
    saved_syncs = get_sync_events()
    editorials = [s for s in saved_syncs if s['is_editorial']]
    print('[*] Editoriales sincronizados: ' + str(len(editorials)))

    print('')
    print('=' * 60)
    print('FASE 5: Analitica de palabras')
    print('=' * 60)
    windows = config.get('analytics', {}).get('word_windows', [3, 5, 7])
    frequencies = compute_frequencies(db_articles, windows)

    for days in windows:
        word_count = sum(len(v) for v in frequencies[days].values())
        print('  [' + str(days) + 'd] ' + str(word_count) + ' palabras clave')

    trends = compute_trending(frequencies)
    if trends:
        for lang, words in trends.items():
            top = list(words.keys())[:5]
            print('  [TRENDING ' + lang + '] ' + ', '.join(top))

    print('')
    print('=' * 60)
    print('FASE 6: Enriquecimiento LLM')
    print('=' * 60)
    llm_cfg_tmp = config.get('llm', {}).get('production' if mode == 'production' else 'test', {})
    llm = LLMProvider(mode, groq_model=llm_cfg_tmp.get('groq_model', 'llama-3.3-70b-versatile'))
    enriched_count = 0
    for cid, cdata in list(active_clusters.items())[:5]:
        titles_list = [a['title'] for a in cdata['articles']]
        try:
            summary = llm.label_cluster(titles_list)
            detailed = llm.summarize_cluster(titles_list)
            cdata['summary'] = summary
            cdata['detailed'] = detailed
            enriched_count += 1
            print('  [OK] Cluster ' + str(cid) + ': ' + str(summary)[:60] + '...')
        except Exception as e:
            print('  [WARN] Cluster ' + str(cid) + ': LLM fallo (' + str(e) + ')')
            errors.append('LLM cluster ' + str(cid) + ': ' + str(e))

    print('')
    print('=' * 60)
    print('FASE 9: Analisis de Narrativa')
    print('=' * 60)
    stance_data = {}
    coordination_flags = []
    actor_mentions = detect_actor_mentions(db_articles)
    print('  Actores detectados: ' + str(len(actor_mentions)))
    for actor, arts in sorted(actor_mentions.items()):
        print('    ' + actor + ': ' + str(len(arts)) + ' articulos')
    if actor_mentions and mode == 'production':
        try:
            stance_data = aggregate_stance(actor_mentions, llm)
            for actor, sources in stance_data.items():
                total = sum(sum(v.values()) for v in sources.values())
                print('  [OK] ' + actor + ': ' + str(total) + ' clasificados')
        except Exception as e:
            print('  [WARN] Stance analysis fallo: ' + str(e))
            errors.append('Stance: ' + str(e))
    if sync_events:
        coordination_flags = detect_coordination(sync_events, db_articles)
        if coordination_flags:
            print('  [!] Posible coordinacion: ' + str(len(coordination_flags)) + ' eventos')
        else:
            print('  Sin coordinacion detectada')

    print('')
    print('=' * 60)
    print('FASE 7: Generando HTML + JSON')
    print('=' * 60)
    llm_cfg = config.get('llm', {}).get('test' if mode == 'test' else 'production', {})
    llm_model = llm_cfg.get('ollama_model') or llm_cfg.get('groq_model')
    generate_briefing(db_articles, active_clusters, sync_events, frequencies, trends, date_str=date_str, all_articles_in_window=db_articles, sources=config['sources'], llm_model=llm_model,
                      wordclouds={}, breaking=[], entities={},
                      feed_status=feed_status, stance_data=stance_data,
                      coordination_flags=coordination_flags,
                      site_domain=config.get('deploy', {}).get('site_domain'),
                      is_index=True)

    for i in range(1, 7):
        ds = (now - timedelta(days=i)).strftime('%y%m%d')
        generate_briefing(db_articles, active_clusters, sync_events, frequencies, trends, date_str=ds, all_articles_in_window=db_articles, sources=config['sources'], llm_model=llm_model,
                          wordclouds={}, breaking=[], entities={},
                          feed_status=feed_status, stance_data=stance_data,
                          coordination_flags=coordination_flags,
                          site_domain=config.get('deploy', {}).get('site_domain'),
                          is_index=False)
    generate_clusters_page(active_clusters, date_str)
    generate_json_data(db_articles, active_clusters, sync_events, frequencies, trends, date_str)

    print('')
    print('=' * 60)
    print('FASE 8: Deploy')
    print('=' * 60)
    deploy(mode, config.get('deploy', {}))

    status_msg = '<b>daily_news completado</b>\n'
    status_msg += str(len(all_articles)) + ' articulos | ' + str(len(active_clusters)) + ' clusters\n'
    status_msg += 'DB: ' + str(len(db_articles)) + ' en ventana'
    if errors:
        status_msg += '\n' + str(len(errors)) + ' warnings'
    notify_telegram(status_msg)

    print('')
    print('=' * 60)
    print('[OK] Proceso completado')
    print('=' * 60)


if __name__ == '__main__':
    fast = '--fast' in sys.argv
    main(fast=fast)
