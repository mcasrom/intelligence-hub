# Way Ahead · Intelligence Hub

## Status actual (24 Julio 2026)

### Pipeline
- [x] Scraping RSS: 15 fuentes, 7 países (ES, US, FR, UK, IT, DE, BR)
- [x] Embeddings: TF-IDF (fallback automático si no hay Gemini API)
- [x] Clustering: HDBSCAN, 28 clusters detectados
- [x] Sincronizadas: detección de noticias coordinadas entre medios
- [x] Analítica: palabras clave ventanas 3d/5d/7d, trending por idioma
- [x] Enriquecimiento LLM: Groq (llama3-70b-8192)
- [x] Generación HTML+JSON: briefing diario, clusters, data.json
- [x] Deploy local: copia a /var/www/daily_readings/ (sudo cp)
- [x] Cron: 00:00, 06:00, 12:00, 18:00

### Repositorio
- **URL:** https://github.com/mcasrom/intelligence-hub
- **Rama:** main
- **Stack:** Python 3.12 + scikit-learn + feedparser + Groq + Jinja2
- **Tamaño:** 736KB (código) + 469MB (venv) + 128KB (SQLite DB)

### Despliegue
- **Servidor:** Hetzner (178.105.80.193), usuario deploy
- **Ruta:** /home/deploy/intelligence-hub/
- **Web:** https://news.viajeinteligencia.com/ (estáticos en /var/www/daily_readings/)
- **PM2:** No necesario (cron-based)
- **Base de datos:** SQLite en data/news.db (146 artículos en ventana 7d)

### Consumo de recursos
- **Disco:** ~470MB (469MB venv + 736KB código + 128KB DB + 400KB output)
- **RAM:** ~150-200MB durante ejecución del pipeline
- **CPU:** ~10-30s por ciclo completo (depende de Groq)
- **API:** Groq (llama3-70b-8192) ~5-10 requests por ciclo
- **Red:** ~2-5MB por ciclo (RSS feeds)

### Fuentes configuradas (15)
| País | Medios |
|------|--------|
| España | El País, El Mundo, La Vanguardia, El Diario Cantabria |
| EE.UU. | Washington Post, WSJ |
| Francia | Le Monde, Le Figaro |
| Reino Unido | BBC News, The Guardian |
| Italia | Corriere della Sera, Il Sole 24 Ore |
| Alemania | Der Spiegel, Deutsche Welle |
| Brasil | Folha de S.Paulo |

## Pendientes / Mejoras

### Corto plazo
- [ ] Añadir más fuentes por país (mínimo 3-4 por país)
- [ ] Configurar GEMINI_API_KEY para embeddings de calidad (vs TF-IDF)
- [ ] Rotación 7 días de artículos en BD (actualmente retiene todo)
- [ ] Healthcheck endpoint para monitorizar el cron
- [ ] Logs rotativos (actualmente crecen sin límite)

### Medio plazo
- [ ] Dashboard de monitorización (último ciclo, errores, stats)
- [ ] Alertas si el pipeline falla (Telegram/email)
- [ ] Tests unitarios del pipeline
- [ ] Backup automático de la BD
- [ ] Purgado de artículos > 30 días
- [ ] Caché Redis para rate limiting entre ciclos

### Largo plazo
- [ ] API pública de datos (read-only)
- [ ] Frontend dinámico (React/Vue) vs estático actual
- [ ] Fuentes por suscripción (selección de países/medios por usuario)
- [ ] Alertas temáticas personalizadas
- [ ] ML fine-tune para clasificación de narrativas

## Bugs conocidos
- Groq devuelve 400 en algunos clusters (modelo o rate limit)
- Sin GEMINI_API_KEY, embeddings usan TF-IDF (menor calidad de clustering)
- deploy.py requiere sudo (configurar sudoers sin password)
