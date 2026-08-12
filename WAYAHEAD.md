# Way Ahead · Intelligence Hub

## Status actual (27 Julio 2026)

### Pipeline
- [x] Scraping RSS: 18 fuentes, 7 países (ES, US, FR, UK, IT, DE, BR)
- [x] Embeddings: TF-IDF char-wb ngrams(2,4) 500d (fallback automático)
- [x] Clustering: HDBSCAN, ~250 clusters detectados por ventana
- [x] Sincronizadas: detección de noticias coordinadas entre medios (coseno ≥ 0.75)
- [x] Analítica: palabras clave ventanas 3d/5d/7d, trending por idioma (6 idiomas)
- [x] Enriquecimiento LLM: Groq (llama-3.3-70b-versatile) con truncado y JSON keys corregidas
- [x] Narrativa: stance detection pro/contra/neutral por actor geopolítico (Russia, China, USA, EU, Iran, Israel, Ukraine)
- [x] Coordinación editorial: detección de ventana temporal < 6h entre fuentes cubriendo mismo tema
- [x] Generación HTML+JSON: briefing diario, clusters, data.json, archivo 7 días
- [x] Deploy local: rsync a /var/www/daily_readings/ + chown
- [x] Cron: cada 6h (00:00, 06:00, 12:00, 18:00) con notificación Telegram
- [x] Counter service: PM2, visitantes únicos con SQLite, health endpoint
- [x] PWA: instalable en móviles y tablets con service worker

### Repositorio
- **URL:** https://github.com/mcasrom/intelligence-hub
- **Rama:** main
- **Stack:** Python 3.12 + scikit-learn + HDBSCAN + feedparser + Groq + Jinja2 + Chart.js
- **Tamaño:** ~800KB (código) + ~470MB (venv) + ~828KB (SQLite DB)

### Despliegue
- **Servidor:** Hetzner (178.105.80.193), usuario deploy
- **Ruta:** /home/deploy/intelligence-hub/
- **Web:** https://news.viajeinteligencia.com/ (estáticos en /var/www/daily_readings/)
- **Nginx:** SSL Let's Encrypt, redirect HTTP→HTTPS, denial de archivos sensibles
- **PM2:** intelligence-hub-counter (puerto 9099)
- **Base de datos:** SQLite WAL mode en data/news.db (~1420 artículos en ventana 7d)
- **GitHub backup:** push automático tras deploy (token personal)

### Consumo de recursos
- **Disco:** ~470MB (469MB venv + ~800KB código + ~828KB DB + ~1.8MB output)
- **RAM:** ~150-200MB durante ejecución del pipeline; 21MB counter service (permanente)
- **CPU:** ~30-60s por ciclo completo (depende de Groq y volumen de embeddings)
- **API:** Groq (llama-3.3-70b-versatile) ~10-15 requests por ciclo (5 clusters + N artículos para stance)
- **Red:** ~2-5MB por ciclo (RSS feeds) + ~88KB por deploy rsync
- **Caché:** FeedCache TTL 30min, STANCE_CACHE en memoria por ciclo

### Fuentes configuradas (18)
| País | Medios |
|------|--------|
| España | El País, El Mundo, La Vanguardia, El Diario Cantabria |
| EE.UU. | NYT, Washington Post, WSJ, Fox News |
| Francia | Le Monde, Le Figaro |
| Reino Unido | BBC News, The Guardian |
| Italia | Corriere della Sera, Il Sole 24 Ore |
| Alemania | Der Spiegel, Deutsche Welle |
| Brasil | Folha de S.Paulo, G1 Globo |

## Pendientes / Mejoras

### Corto plazo — Sprint actual: conseguir más Media News
- [ ] **Ampliar fuentes RSS:** añadir más medios por país (Reuters, AP, AFP, Al Jazeera, RT, Sputnik, etc.)
- [ ] **Ampliar actores geopolíticos:** India, Turquía, OTAN, Corea del Norte, Arabia Saudí
- [ ] **Mejorar stance detection:** prompt multilingüe + few-shot + confidence score
- [ ] **Healthcheck endpoint público:** /api/health con estado del pipeline
- [ ] **Logs rotativos:** actualmente cron.log crece sin límite
- [ ] **Dashboard de monitorización:** último ciclo, errores, stats, gráficas semanales

### Medio plazo
- [ ] **Noticias destacadas (breaking news):** detección de crecimiento súbito de keywords
- [ ] **Alertas Telegram por evento:** cuando un tema se sincroniza en ≥3 fuentes en < 1h
- [ ] **Backup automático de BD:** rsync diario a backup remoto o S3
- [ ] **Purgado de artículos > 30 días:** rotación actual solo limpia 7 días
- [ ] **API pública de datos:** endpoints REST para consultar artículos, clusters, syncs
- [ ] **Frontend dinámico:** filtros por actor, fuente, fecha; gráficos interactivos
- [ ] **Suscripciones por tema:** alertas personalizadas cuando un actor/país aparece con cierto sesgo

### Largo plazo
- [ ] **ML fine-tune para clasificación de narrativas:** modelo propio vs LLM externo
- [ ] **Fine-Grained stance:** detectar no solo pro/contra sino tipo de framing (victimización, amenaza, oportunidad, etc.)
- [ ] **Análisis de redes de fuentes:** qué medios se citan entre sí, detección de cámaras de eco
- [ ] **Interfaz multi-usuario:** selección de países/medios/temas por perfil

## Bugs conocidos (resueltos)
- ~~Groq devuelve 400 en algunos clusters (modelo o rate limit)~~ → Corregido: JSON keys con quotes en prompt + truncado de títulos
- ~~Sin GEMINI_API_KEY, embeddings usan TF-IDF (menor calidad)~~ → TF-IDF funciona aceptablemente con char-ngrams
- ~~deploy.py requiere sudo~~ → Configurado sudoers sin password para rsync
- ~~Solo 5 clusters pasados al generador (resto ignorados)~~ → Ahora todos los active_clusters se renderizan
- ~~FutureWarning HDBSCAN copy parameter~~ → Añadido copy=True

## Bugs conocidos (abiertos)
- Fox News feed puede devolver 0 artículos en fines de semana
- Groq 400 en ~5 clusters por ciclo (moderación de contenido, no crítico)
- CNN feed devuelve artículos de 2023 (reemplazado por Fox News)

## Changelog

### 2026-07-27
-  — stance detection (pro/contra/neutral) por actor geopolítico
- Coordinación editorial: detección de sincronización < 6h entre fuentes
- Secciones nuevas en web: Cobertura por bloque + Posible coordinación
-  — FASE 9: Análisis de Narrativa (7 actores, 630 arts clasificados)
- Fix: todos los active_clusters se pasan al generador (antes solo los 5 enriquecidos con LLM)
- Fix: copy=True en HDBSCAN (elimina FutureWarning de sklearn 1.10)
- Fix: JSON keys con quotes en prompt LLM (evita 400 de Groq por sintaxis inválida)
- Fix: deploy.py usa rsync en vez de cp -r
- Mejora: counter_server.py con health endpoint + visitantes únicos con SQLite
- Commit: 079eeda

### 2026-07-26
- Fix: añadir formato fecha con microsegundos para DW y feeds ISO
- Fix: Der Spiegel feed a edición alemana activa, DW usa updated como fallback
- Fix: reemplazar CNN (RSS roto, contenido 2023) por Fox News
- Fix: stopwords con tildes, sync_events sources/countries como listas
- Fix: artículos filtrados por fecha en cada edición + stopwords ampliadas
- Feat: KPI chart 7 días con Chart.js
- Feat: PWA instalable en móviles + service worker
- Feat: funnel guide modal interactivo
- Feat: diagnóstico de fuentes en dashboard

## OPERACIONES — Infraestructura (31 Jul 2026)
- **Fuente de verdad unica**: GitHub `mcasrom/intelligence-hub`. El servidor `deploy@178.105.80.193` ejecuta el pipeline (cron `0,6,12,18 UTC` con `run.sh`, healthcheck cada 30 min) y ahora puede **pushear directo** con la deploy key write `~/.ssh/ih-deploy-key` (host alias `github.com-ih`).
- Flujo: editar en el servidor → `git add -A && git commit && git push origin main`. Sin clones de desktop ni patches. La vieja `ikm-deploy-key` (`github.com-ikm`) queda como read-only backup de `mcasrom/ikm`.
- El resumen/estado de sesion vive en `~/org/260731_wayahead.org` del desktop y tambien se versiona aqui.
## Sprint 11 — Event Dossier Engine (MVP, caso Ceuta) (10 Ago 2026)

- **Nuevo módulo `/home/deploy/event-dossier`** (repo `mcasrom/event-dossier`): servicio satélite del Intelligence Hub que abre dossiers vivos de hechos noticiable persistentes.
- **Máquina de estados**: CANDIDATO→ACTIVO→EN_ENFRIAMIENTO→CERRADO→ARCHIVADO (+REABIERTO con capítulos), DESCARTADO. CLI `event_dossier.py open/close/status/reactivate`.
- **DB SQLite** `data/events.db`: events, event_chronology, event_actors, event_sources, event_synthesis + event_fulltext_cache.
- **Pipeline** `pipeline.py` (cron `20 */6 * * *`): lee los 8 feeds del hub por keywords → trafilatura fulltext → LLM Groq (llama-3.3-70b) extracción estructurada (§8.1) → dedup MiniLM on-demand → merge → síntesis periódica (§8.2) → render Jinja2 → `/evento/<slug>.html`.
- **Caso Ceuta en vivo**: `ceuta-valla-2026` ACTIVO — 31 entradas cronología, 61 actores, 10 fuentes, síntesis generada. Página: `https://viajeinteligencia.com/evento/ceuta-valla-2026.html` (tabs Resumen/Cronología/Actores/Estado/Fuentes, badge 🔴 En seguimiento, disclaimer metodología).
- **Recursos**: 0 proceso residente (cron + CLI), MiniLM on-demand (se libera tras dedup), RAM estable (sin crecimiento de swap). Nginx: location `/evento/` en vhost landing.
- **Commit**: `94a0028`. Coste ~0 (Groq + trafilatura, todo gratuito).

## Sprint 11b — Event Dossier: fix de calidad (10 Ago 2026)

- **Bug detectado**: la cronología incluía entradas totalmente ajenas (festival de Arlés, ovnis de los 70, historia de Bukele en El Salvador, casa-museo de Gainsbourg). Causa: (1) el filtro de artículos matcheaba keywords en la descripción completa del RSS (no solo título), y (2) el LLM extraía cronología de artículos tangenciales que solo mencionaban el evento de pasada o comparaciones históricas.
- **Fixes**:
  - `fulltext_fetcher.extract_links` ahora exige ≥1 keyword en el TÍTULO (no solo descripción).
  - `pipeline.py`: filtro DURO post-LLM — toda entrada de cronología debe mencionar ≥1 keyword del evento; si no, se descarta.
  - `event_analyzer.EXTRACT_SYSTEM`: instrucciones explícitas de ignorar contexto/comparaciones históricas/temas tangenciales.
  - Límite de artículos por ciclo: 10 → 5 (preservar cuota diaria de Groq).
- **Limpieza de BD**: borradas 34 entradas espurias (queda 23, todas sobre migración/Ceuta/frontera).
- **⚠️ Cuota Groq**: límite 100k TPD alcanzado (99.2k usados) → respuestas vacías/429. El pipeline salta la síntesis con try/except; la cuota se restablece ~1h después. Considerar límite por ciclo más bajo o modelo más barato.
- **Commit**: `58364cd`.
## Sprint 11c — Event Dossier Engine: PROYECTO CANCELADO (10 Ago 2026)

- **Veredicto del usuario: FRAUDE / basura / proyecto cancelado.** El módulo `event-dossier` se retira por completo.
- **Razones**: el pipeline automático LLM-sobre-feeds-RSS produce cronología sucia — el LLM inventa/rellena entradas ajenas al evento (comparaciones históricas tipo Trump/El Salvador, cine, cultura) y asigna confidence 0.5 a todo ("⚠️ sin confirmar" en cada línea). No sirve como dossier de inteligencia para analistas.
- **Lección**: una cronología de un hecho serio necesita fuentes primarias verificadas y selección editorial, NO un LLM escupiendo feeds internacionales. La automatización de análisis de hechos noticiables requiere curaduría humana de la línea base + LLM solo para redactar sobre datos ya verificados.
- **Limpieza completa**: cron eliminado, location nginx /evento/ eliminado, /var/www/.../evento/ borrado, /home/deploy/event-dossier borrado, repo GitHub mcasrom/event-dossier borrado, página 404.
- **Estado**: no queda rastro del módulo. Coste incurrido: solo cuota de Groq (gratuita) + tiempo.

- **VALORACIÓN FINAL (10 Ago, tras limpieza completa)**: la IA DeepSeek fue INCAPAZ de elaborar un proyecto mínimo viable. El resultado fue un fraude: cronología inventada (Trump/El Salvador/Venezuela a 8.000 km del evento), confidence 0.5 asignada a todo, y sin análisis de briefing. Se elimina el proyecto en su totalidad. **Lección: NO usar DeepSeek para construir sistemas de análisis de hechos noticiables.** Limpieza completa verificada: sin cron, sin nginx location, sin archivos, sin venv residual (trafilatura desinstalada), hub intacto.

## Nota — Servicio anonimizacion.viajeinteligencia.com (puerto 5000) PARADO a propósito

- **Estado**: backend (puerto 5000) sin proceso escuchando → el vhost devuelve 502.
- **Motivo (decisión del usuario)**: el servicio está **parado deliberadamente por el usuario** por dudas sobre su funcionamiento. NO es un fallo ni hay que levantarlo.
- **Fecha**: vhost creado 23-Jul-2026; parado por decisión propia, no por error.
- **Acción**: NO tocar / NO arrancar / NO intentar arreglar hasta que el usuario lo decida.

## Sprint — Plan 30 días fase 1-3 + demos (10 Ago 2026, cierre)

- **Fase 1 · Country**: copy sin "OSINT" (home + 217 fichas) + 3 artículos comparativos (España-Marruecos-Portugal, Top 10 seguros, países baratos) + sitemap 222 URLs + IndexNow.
- **Fase 2 · NearMe**: 2 landing pages `/incendios` (NASA FIRMS) y `/trafico` (DGT) + sitemap 6 URLs + IndexNow.
- **Fase 3 · MyIP**: 2 posts `/fuga-dns` y `/vpn-check` + rutas server + sitemap 4 URLs + IndexNow + fix pantalla en blanco PWA (dist roto, SW v4).
- **Pack de posts RRSS**: `pack_posts_2026.md` (X, Reddit, Bluesky, Mastodon) para las 3 estrellas.
- **Demos**: `~/Desktop/demo/` (laptop) — 4 screenshots + 3 videos MP4 (nearme timeline con 502 eventos, myip guía vpn-check scroll, country zoom). Nota: el análisis real de myip (progreso VPN/DNS) no arranca en headless (queda en 0%, requiere flujo/auth); el video usa la guía /vpn-check.
- **Hito**: landing en v1.0.4 (campaña SEO documentada en CHANGELOG).
- **Pendiente fase 4**: distribución real (X/Reddit/Bluesky/Mastodon con las plantillas + capturas/videos).

## Decisión — Estrategia de distribución RRSS (10 Ago 2026)

- **Canales activos**: X, Mastodon y Bluesky (publicando con el pack `pack_posts_2026.md` + números vivos de cada página).
- **Reddit descartado** por decisión del usuario: comunidad paranoica, alto coste de esfuerzo y bajo retorno para este ecosistema. No se publicará allí de forma sistemática.
- **Dato de interés**: el post `/trafico` de NearMe generó 48 hits reales (2 IPs externas) en su primer día — la keyword "tráfico DGT" tiene demanda. El plan SEO sigue su curso; la distribución activa acelera el resto.

## Sprint — Video del Radar fail2ban para YouTube (10 Ago 2026)

- **Objetivo**: extraer el "video" del radar de myip (294 snapshots de ataques fail2ban) para subirlo a YouTube sin tocar el radar.
- **Cómo**: los 294 snapshots JSON (`/app/data/snapshots/`) se leen vía `/api/threat/timeline`; el radar los reproduce con un slider `onChange` de React. Truco usado: **native setter** de `HTMLInputElement.value` + dispatch input/change para que React re-renderice el mapa en cada snapshot (verificado: contador 1→294, frames todos distintos, el mapa evoluciona).
- **Radar intacto**: solo lectura vía API, no se modificó nada del server.
- **Output en la laptop** `~/Desktop/demo/`:
  - `radar-fail2ban.mp4` (10s, recorrido del slider)
  - `radar-fail2ban-youtube.mp4` (58.8s, 294 snapshots, overlay con ffmpeg drawtext: título "ATAQUES BLOQUEADOS EN TIEMPO REAL", subtítulo, rango "29 Jul → 10 Ago 2026", marca viajeinteligencia.com)
- **Veredicto usuario**: "es perfecto, no necesitamos nada más".
- **Hito**: landing sigue en v1.0.4 (el video no tocó el server).

## Sprint — Radar: selección por clic + tiles Carto (11 Ago 2026)

- **Problema reportado**: la selección en el mapa del radar era "lenta o nula" + warnings `mozPressure/mozInputSource` (avisos estándar de Leaflet 1.9.4 con Firefox, inofensivos).
- **Causa real**: el radar NO tenía handler de clic — la zona solo se seleccionaba con botones de radio (50/200/500 km) o geolocalización. Hacer clic en el mapa no hacía nada.
- **Fix** (commit `117d0c1`):
  - `map.on(click)` → `setPos(lat, lon, Zona seleccionada)` + marcador temporal ámbar en el punto clicado.
  - Tiles: `tile.openstreetmap.org` → `basemaps.cartocdn.com/dark_all` (más rápidos, estilo oscuro coherente con myip/country).
- **Verificado** con puppeteer: clic cambia currentLat/Lon (40.42→39.01), label "Zona seleccionada", eventos recargados (25→15), 0 errores JS.
- **Seguro de vida**: backup index.html antes de editar. Ecosistema intacto.

## Sprint — Radar: fix radio + selección clic + incendios (11 Ago 2026)

- **Radio 200 vs 500 daban los MISMO datos** (0/8/9/1). Causa: el API respeta el radio, pero con `limit=500` fijo, ambos radios devolvían los mismos 500 eventos MÁS CERCANOS (los del centro de Madrid).
- **Fix**: `load()` ahora usa `limit` según radio (50→800, 200→1500, 500→3000). Verificado: radio 200 = 154 marcadores (6 críticas, 26 incendios); radio 500 = 748 (34 críticas, 369 incendios). El radio se nota.
- **Incendios no se veían**: al cambiar el filtro a solo critical/alert/warning, los fuegos de NASA FIRMS (nivel info) desaparecían. Fix: filtrar critical/alert/warning + **siempre fire/earthquake**.
- **Selección por clic** (2 fixes previos): `map.on(click)` + `m.on(click)` en marcadores (antes los marcadores con z-index alto tapaban el mapa y el clic no disparaba).
- **Tiles Carto** (rápidos, dark, coherentes con myip/country).
- **Commits**: `53d5e62`, `6e12df8`. Ecosistema verificado intacto.
- **Nota rendimiento**: radio 500 = 748 marcadores (posible clustering si se nota lag).

## Sprint — Radar de Emergencias: fixes completos (11 Ago 2026)

- **5 bugs resueltos** (commits `117d0c1` → `50d8c53`):
  1. **Clic bloqueado por el layer CCAA**: el mapa territorial con `bindPopup` interceptaba el clic y abría su popup ("Castilla-La Mancha: críticas 0...") en vez de seleccionar. Fix: `interactive: false` en el layer CCAA → el clic ahora dibuja el punto con radio.
  2. **Punto de selección no se veía**: el marcador ámbar solo se creaba en clic de mapa. Movido a `setPos()` → visible en clic de mapa, clic de marcador y "Mi ubicación".
  3. **Radio 200 y 500 daban los mismos datos**: el API filtra por radio pero con `limit=500` fijo devolvía los 500 más cercanos. Fix: limit crece con el radio (50→800, 200→1500, 500→3000). Verificado: 200=154 marcadores, 500=748.
  4. **Incendios no se veían**: al filtrar solo critical/alert/warning, los fuegos de NASA FIRMS (nivel info) desaparecían. Fix: incluir `fire`/`earthquake` siempre.
  5. **Tiles lentos**: OSM → Carto dark (coherente con myip/country).
- **Estado**: radar funcional — clic selecciona con radio, 50/200/500 varían, incendios/sismos visibles.
- **Seguro de vida**: backup `index.html.bak-20260811` local + push a GitHub.
- **PRÓXIMO SPRINT (12 Ago)**: valorar las visitas de HOY al ecosistema (analytics/logs) tras los fixes + el pico del eclipse.

## Sprint — VI Intelligence Agent (MVP) (11 Ago 2026)

- **Nuevo microservicio `vi-agent`** (repo `mcasrom/vi-agent`, commit `46bf827`): capa de inteligencia sobre los microservicios existentes. El usuario pregunta en lenguaje natural y el agente decide qué herramientas usar.
- **5 herramientas REST reales** (reutilizan APIs existentes): get_country (Country, 44 indicadores), get_incidents (NearMe por coords), geocode (Nominatim), get_sky (Eclipse), get_news (Intel Hub).
- **Agente**: LLM externo Groq (llama-3.3-70b), sin LLM local, sin shell. Límites estrictos: máx 4 iteraciones, 6 llamadas tool, timeouts, rate limit 20/min/IP, cache SQLite con TTL por categoría.
- **Web mínima**: `https://www.viajeinteligencia.com/agente/` (path de la landing, sin DNS nuevo) — input + respuesta + fuentes.
- **Correcciones clave durante el desarrollo**: (1) el LLM no respondía JSON puro → parseToolCall robusto (primer JSON válido, no greedy); (2) prompt estricto con parámetros exactos de cada tool; (3) separación [DATO]/[INFERENCIA] con fuente.
- **Verificado**: "Australia en abril" → informe con datos reales (población 27M, IDH, esperanza de vida) y [INFERENCIA] honesta; "Murcia ahora" → geocode + 31 incidentes (calidad aire PM10, UV 8, ola de calor). Ecosistema intacto.
- **Consumo**: 68MB PM2, carga ~0. Coste LLM ~0 (Groq).
- **PM2**: `vi-agent` (puerto 3320). **Seguro de vida**: repo GitHub.

## Sprint — SEO del VI Agent + CTA + footer (11 Ago 2026)

- **2 artículos SEO** en la landing (commit `975a6c6`):
  - `/agente-inteligencia-viaje` — "Agente de inteligencia de viaje gratis" con demo interactiva integrada (fetch al agente real).
  - `/que-pasa-en-tu-ciudad-ahora` — keyword local con tabla de fuentes + 2 CTAs.
- **CTA hero** "🧠 Pregúntale al agente" (verde, primero).
- **Footer**: enlaces al agente, artículos, contacto, ecosistema.
- **Sitemap**: 13 → 16 URLs. IndexNow 200.
- **Nginx**: locations para las URLs limpias de los 2 artículos.
- **Hito**: v1.1.1.
- **Seguro de vida**: backups index.html + sitemap antes de editar. Ecosistema verificado 200.
- **Próximo**: valorar visitas del 12-Ago (eclipse) + medir uso real del agente.

## Sprint — Bot Telegram del VI Agent + posts eclipse (12 Ago 2026)

- **Bot `@Vi_intelligence_bot`** (PM2 `vi-agent-bot`): responde preguntas del agente por Telegram con long polling.
- **Mejoras**: descripción/about configurados, contexto conversacional (recuerda el chat, MAX 6), comando `/clear`, `/help`. Soporte de `context` en `/api/ask`.
- **Bug getUpdates**: `setInterval` lanzaba polls superpuestos → "Conflict". Fix: bucle secuencial `pollLoop` (nunca 2 getUpdates a la vez).
- **Seguridad**: `.env` (con token) sacado de git. ⚠️ El token quedó en el historial de un commit privado — opcional rotar con @BotFather.
- **Posts eclipse 12-Ago** (`120826_eclipse_posts.md`): nubosidad actualizada (despejado Oviedo/León/Burgos/Soria/Zaragoza/Teruel/Palma) + post del agente.
- **Hito**: v1.1.3.
- **Próximo sprint (pendiente)**: bot más potente — menú con botones (inline keyboards), comandos rápidos, y mejorar UX.

## Sprint — Fix noticias Country + menú del bot (12 Ago 2026)

- **Fix noticias de Country** (commit `0a0f4b7`): para países sin `news_query` mapeado, usaba el código ISO (2 letras) como búsqueda → "SY" coincidía con Sydney/Symphony/eventos deportivos. Fix: usar el nombre real del país de geo.json ("Syrian Arab Republic"). Verificado: Siria y Mozambique devuelven noticias relevantes.
- **Bot Telegram — menú** (commit `b3a43de`): inline keyboard con botones (Riesgo país, Qué pasa en mi ciudad, Comparar destinos, Incendios cerca, /clear, /help). Los botones disparan preguntas de ejemplo al agente. Callbacks manejados.
- **Nota**: foto de perfil del bot subida por el usuario vía @BotFather.

