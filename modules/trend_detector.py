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
import requests
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pytrends.request import TrendReq
from config import NEWS_API_KEY

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
