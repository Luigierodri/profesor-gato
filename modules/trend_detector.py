"""
trend_detector.py — Detector de Temas Virales para LATAM/México
Proyecto: Profesor Gato

Fuentes (en orden de confianza):
  1. Google Trends — trending searches México/LATAM (pytrends)
  2. NewsAPI       — titulares de alto impacto en español
  3. Reddit        — subreddits educativos hispanohablantes

Flujo de uso:
  - detectar_temas_del_dia() → lista de candidatos rankeados
  - sugerir_tema_interactivo() → muestra opciones y devuelve el elegido
"""

import sys
import json
import requests
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import anthropic
from pytrends.request import TrendReq
from config import NEWS_API_KEY, ANTHROPIC_API_KEY, CLAUDE_MODEL

GEOS_LATAM = ["mexico", "argentina", "colombia", "chile", "peru"]


# ─── GOOGLE TRENDS ────────────────────────────────────────────────────────────

def obtener_trends_google(paises: list[str] = None, limite: int = 10) -> list[dict]:
    if paises is None:
        paises = GEOS_LATAM  # todos los países LATAM
    resultados = {}
    try:
        pytrends = TrendReq(hl="es-MX", tz=360, timeout=(10, 30))
        for pais in paises:
            try:
                df = pytrends.trending_searches(pn=pais)
                for tema in df[0].tolist():
                    resultados[tema] = resultados.get(tema, 0) + 1
            except Exception:
                pass
        # Score = cuántos países comparten el trending
        temas = [
            {"tema": t, "fuente": "Google Trends", "score": 3 + v, "paises": v}
            for t, v in sorted(resultados.items(), key=lambda x: -x[1])
        ]
        print(f"  Google Trends: {len(temas)} temas de {len(paises)} países")
        return temas[:limite]
    except Exception as e:
        print(f"  Google Trends error: {e}")
        return []


# ─── NEWS API ─────────────────────────────────────────────────────────────────

_CATEGORIAS_NEWS = [
    "general", "sports", "entertainment", "science", "technology", "health"
]

def obtener_noticias_educativas(limite: int = 12) -> list[dict]:
    if not NEWS_API_KEY:
        return []
    url = "https://newsapi.org/v2/top-headlines"
    temas = []
    for categoria in _CATEGORIAS_NEWS:
        try:
            resp = requests.get(url, params={
                "language": "es", "country": "mx",
                "category": categoria, "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            }, timeout=10)
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                if a.get("title") and a.get("description"):
                    temas.append({
                        "tema": a["title"],
                        "fuente": f"NewsAPI/{categoria}",
                        "score": 2,
                    })
        except Exception:
            pass
    print(f"  NewsAPI: {len(temas[:limite])} noticias")
    return temas[:limite]


# ─── REDDIT ───────────────────────────────────────────────────────────────────

_SUBREDDITS_ES = [
    "mexico", "es", "colombia", "argentina",
    "futbol", "deportes", "noticias", "latinoamerica",
    "ciencia", "historia",
]

def obtener_reddit_educativo(limite: int = 10) -> list[dict]:
    temas = []
    headers = {"User-Agent": "ProfesorGato/2.0"}
    for sub in _SUBREDDITS_ES[:6]:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
            resp = requests.get(url, headers=headers, timeout=10)
            for post in resp.json()["data"]["children"]:
                titulo = post["data"]["title"]
                score_reddit = post["data"].get("score", 0)
                if len(titulo) > 15:
                    temas.append({
                        "tema": titulo,
                        "fuente": f"Reddit/r/{sub}",
                        "score": 1 + min(2, score_reddit // 1000),
                    })
        except Exception:
            pass
    print(f"  Reddit: {len(temas[:limite])} posts")
    return temas[:limite]


# ─── BOOST DE VIRALIDAD ───────────────────────────────────────────────────────

_KEYWORDS_BOOST = [
    # Deportes / Mundial 2026
    "mundial", "world cup", "copa", "futbol", "fútbol", "liga", "champions",
    "olimpiadas", "olimpicos",
    # Política LATAM
    "elecciones", "elección", "vota", "candidato", "presidente", "colombia",
    "mexico", "méxico", "venezuela", "argentina", "chile",
    # Fenómenos urbanos / ciencia viral
    "hunde", "hundimiento", "terremoto", "temblor", "volcán", "volcan",
    "cdmx", "ciudad de mexico",
    # Cultura pop / entretenimiento
    "taylor swift", "netflix", "viral", "tendencia",
]

def _aplicar_boost(candidatos: list[dict]) -> list[dict]:
    """Suma +2 al score si el tema contiene keywords de alta viralidad."""
    for c in candidatos:
        tema_lower = c["tema"].lower()
        if any(kw in tema_lower for kw in _KEYWORDS_BOOST):
            c["score"] += 2
    return candidatos


# ─── SELECTOR PRINCIPAL ───────────────────────────────────────────────────────

def detectar_temas_del_dia() -> list[dict]:
    """
    Combina todas las fuentes y devuelve los 10 mejores temas del día.
    Los resultados están rankeados: mayor score = más viral en LATAM.
    Cubre deportes, política, ciencia, cultura pop, fenómenos urbanos e historia.
    """
    print("\nDetectando temas virales del dia en LATAM...")
    candidatos = (
        obtener_trends_google() +
        obtener_noticias_educativas() +
        obtener_reddit_educativo()
    )

    # Deduplicar por tema (ignorando mayúsculas)
    vistos, unicos = set(), []
    for c in candidatos:
        key = c["tema"].lower()[:60]
        if key not in vistos:
            vistos.add(key)
            unicos.append(c)

    _aplicar_boost(unicos)
    top = sorted(unicos, key=lambda x: x["score"], reverse=True)[:10]

    if top:
        print("\nTOP TEMAS DEL DIA:")
        for i, c in enumerate(top, 1):
            print(f"  {i}. [{c['fuente']}] {c['tema'][:75]}")
    return top


def seleccionar_angulo_educativo(tendencias: list[dict]) -> dict:
    """
    Dado el listado de tendencias del día, usa Claude para encontrar
    el ángulo educativo más potente conectado a lo que ya está viral.

    El canal explica historia, cultura, sociedad, economía, ciencia —
    NO cubre noticias directas. El trend es el gancho de relevancia;
    el ángulo educativo es lo que realmente se explica en el video.

    Devuelve:
        {
          "angulo_educativo": str,   # tema real del video
          "trend_conectado":  str,   # señal viral que lo dispara
          "razon":            str,   # por qué tiene tracción hoy
        }
    """
    if not tendencias:
        return {"angulo_educativo": None, "trend_conectado": None, "razon": "sin tendencias"}

    lista_str = "\n".join(
        f"- [{c['fuente']}] {c['tema']} (score {c['score']})"
        for c in tendencias[:10]
    )

    prompt = f"""Eres el productor del canal educativo "Profesor Gato" en YouTube Shorts (México/LATAM).

El canal explica: historia, cultura, sociedad, economía, ciencia, fenómenos urbanos.
NO hace videos de noticias directas — explica el PORQUÉ y el trasfondo de lo que pasa.

Trending hoy en México/LATAM:
{lista_str}

Elige UN tema trending y formula el ÁNGULO EDUCATIVO más potente.
El ángulo debe conectarse con algo que hoy está en boca de todos y explicar su trasfondo histórico, cultural, científico o económico.

Ejemplos de conversión trend → ángulo educativo:
- Trend: "Colombia elecciones mañana" → Ángulo: "¿Por qué Colombia ha cambiado tantas veces de constitución?"
- Trend: "CDMX hundimiento" → Ángulo: "¿Por qué se está hundiendo la Ciudad de México?"
- Trend: "Mundial 2026" → Ángulo: "¿Por qué México nunca pasa de cuartos de final en los Mundiales?"
- Trend: "Taylor Swift tour" → Ángulo: "¿Por qué los conciertos se volvieron tan caros?"
- Trend: "Milei economía Argentina" → Ángulo: "¿Qué es la dolarización y por qué asusta tanto?"

Responde SOLO JSON válido, sin markdown:
{{
  "angulo_educativo": "la pregunta o afirmación del video en español",
  "trend_conectado": "el trending topic que usas como gancho de relevancia",
  "razon": "en una frase, por qué este ángulo tiene tracción hoy"
}}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    resultado = json.loads(raw)
    print(f"  Angulo educativo: {resultado['angulo_educativo']}")
    print(f"  Trend conectado:  {resultado['trend_conectado']}")
    print(f"  Razon:            {resultado['razon']}")
    return resultado


def sugerir_tema_interactivo() -> str:
    """
    Muestra los trending topics y permite elegir uno o escribir uno manual.
    Devuelve el tema seleccionado como string.
    Útil cuando se llama el pipeline sin argumento de tema.
    """
    candidatos = detectar_temas_del_dia()

    if not candidatos:
        print("\nSin temas detectados. Escribe el tema manualmente:")
        return input("> ").strip()

    print("\n¿Sobre qué hacemos el video hoy?")
    print("  0. Escribir tema manual")
    for i, c in enumerate(candidatos[:6], 1):
        print(f"  {i}. {c['tema'][:70]}  [{c['fuente']}]")

    try:
        eleccion = int(input("\nElige (0-6): ").strip())
        if eleccion == 0:
            return input("Escribe el tema: ").strip()
        if 1 <= eleccion <= len(candidatos[:6]):
            return candidatos[eleccion - 1]["tema"]
    except (ValueError, IndexError):
        pass

    return candidatos[0]["tema"]


if __name__ == "__main__":
    tema = sugerir_tema_interactivo()
    print(f"\nTema seleccionado: {tema}")
