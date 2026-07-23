import re
from collections import Counter
from datetime import datetime, timedelta

STOPWORDS = {
    "es": ["el", "la", "los", "las", "un", "una", "y", "e", "o", "a", "en", "de",
           "del", "con", "por", "para", "que", "es", "se", "no", "su", "lo", "le",
           "al", "como", "más", "pero", "sus", "este", "entre", "ya", "todo", "esta",
           "tras", "era", "sin", "sobre", "también", "tras", "fue", "ha", "han",
           "hay", "ser", "sido", "dos", "muy", "cada", "sí", "así", "sólo"],
    "en": ["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
           "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
           "has", "have", "had", "do", "does", "did", "will", "would", "could",
           "should", "may", "might", "shall", "can", "its", "it", "as", "at",
           "that", "this", "these", "those", "not", "no", "so", "if", "all",
           "about", "after", "before", "between", "over", "under", "than"],
    "fr": ["le", "la", "les", "un", "une", "des", "du", "de", "et", "est", "sont",
           "dans", "pour", "sur", "avec", "pas", "que", "qui", "dans", "plus",
           "tout", "ses", "son", "sa", "aux", "ces", "cette", "entre", "était",
           "ont", "fait", "être", "avoir", "très", "aussi", "après", "avant"],
    "it": ["il", "lo", "la", "gli", "le", "un", "uno", "una", "del", "della",
           "dei", "delle", "di", "a", "in", "da", "con", "su", "per", "tra",
           "fra", "che", "è", "sono", "non", "si", "anche", "ha", "ho", "hanno",
           "era", "stato", "più", "molto", "dopo", "prima", "sempre"],
    "pt": ["o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
           "dos", "das", "em", "no", "na", "nos", "nas", "para", "por", "com",
           "que", "é", "são", "não", "se", "mais", "mas", "foi", "era", "tem",
           "têm", "está", "estão", "muito", "tudo", "cada", "entre", "após"],
    "de": ["der", "die", "das", "den", "dem", "des", "ein", "eine", "einen",
           "einer", "eines", "und", "oder", "aber", "in", "auf", "mit", "von",
           "für", "an", "aus", "bei", "nach", "um", "über", "ist", "sind", "war",
           "wird", "nicht", "sich", "auch", "noch", "schon", "sehr", "durch"],
}


def extract_keywords(title, lang="es"):
    words = re.findall(r'[a-zA-Záéíóúàèìòùâêîôûäëïöüñçãõ]+', title.lower())
    stop = STOPWORDS.get(lang, [])
    return [w for w in words if w not in stop and len(w) > 2]


def compute_frequencies(articles, windows=[3, 5, 7]):
    result = {}
    for days in windows:
        cutoff = datetime.utcnow() - timedelta(days=days)
        window_articles = [
            a for a in articles
            if a.get("published") and a["published"] >= cutoff.isoformat()
        ]

        lang_counters = {}
        for a in window_articles:
            lang = a.get("lang", "es")
            if lang not in lang_counters:
                lang_counters[lang] = Counter()
            keywords = extract_keywords(a["title"], lang)
            lang_counters[lang].update(keywords)

        result[days] = {}
        for lang, counter in lang_counters.items():
            result[days][lang] = counter.most_common(50)

    return result


def compute_trending(frequencies):
    trends = {}
    if 3 not in frequencies or 7 not in frequencies:
        return trends
    for lang in frequencies[3]:
        current = dict(frequencies[3].get(lang, []))
        previous = dict(frequencies[7].get(lang, []))
        word_scores = {}
        for word, count in current.items():
            prev_count = previous.get(word, 0)
            score = count / (prev_count + 1)
            word_scores[word] = {"current": count, "previous": prev_count, "ratio": round(score, 2)}
        sorted_words = sorted(word_scores.items(), key=lambda x: x[1]["ratio"], reverse=True)
        trends[lang] = dict(sorted_words[:20])
    return trends
