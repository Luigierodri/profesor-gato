"""
Módulo 1 — Detector de Temas Calientes
Detecta los temas más virales del día con potencial educativo.
Fuentes: Google Trends, NewsAPI, Reddit.
"""

import os
import requests
from pytrends.request import TrendReq
from config import NEWS_API_KEY


# ─── GOOGLE TRENDS ────────────────────────────────────────────────────────────

def obtener_trends_google(geo: str = "MX", limite: int = 5) -> list[str]:
    """Obtiene los trending topics de Google Trends para la región dada."""
    try:
        pytrends = TrendReq(hl="es-MX", tz=360)
        df = pytrends.trending_searches(pn="mexico")
        temas = df[0].tolist()[:limite]
        print(f"✅ Google Trends ({geo}): {temas}")
        return temas
    except Exception as e:
        print(f"⚠️  Error Google Trends: {e}")
        return []


# ─── NEWS API ─────────────────────────────────────────────────────────────────

def obtener_noticias_educativas(limite: int = 5) -> list[dict]:
    """
    Obtiene las noticias más relevantes del día con potencial educativo.
    Filtra por categorías: economía, ciencia, tecnología, historia.
    """
    if not NEWS_API_KEY:
        print("⚠️  NEWS_API_KEY no configurada")
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "language": "es",
        "country": "mx",
        "pageSize": 20,
        "apiKey": NEWS_API_KEY
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        articulos = resp.json().get("articles", [])

        # Filtra artículos con contenido sustancial
        filtrados = [
            {
                "titulo": a["title"],
                "descripcion": a.get("description", ""),
                "fuente": a["source"]["name"]
            }
            for a in articulos
            if a.get("title") and a.get("description")
        ]

        print(f"✅ NewsAPI: {len(filtrados)} noticias encontradas")
        return filtrados[:limite]

    except Exception as e:
        print(f"⚠️  Error NewsAPI: {e}")
        return []


# ─── REDDIT ───────────────────────────────────────────────────────────────────

def obtener_reddit_educativo(limite: int = 5) -> list[str]:
    """
    Obtiene posts populares de subreddits educativos.
    Usa la API pública sin autenticación (read-only).
    """
    subreddits = [
        "todayilearned", "explainlikeimfive",
        "interestingasfuck", "history", "economics"
    ]
    temas = []

    headers = {"User-Agent": "ProfesorGato/1.0"}

    for sub in subreddits[:2]:   # Limita requests
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
            resp = requests.get(url, headers=headers, timeout=10)
            posts = resp.json()["data"]["children"]
            for post in posts:
                titulo = post["data"]["title"]
                if len(titulo) > 20:
                    temas.append(titulo)
        except Exception as e:
            print(f"⚠️  Error Reddit r/{sub}: {e}")

    print(f"✅ Reddit: {len(temas[:limite])} temas encontrados")
    return temas[:limite]


# ─── SELECTOR PRINCIPAL ───────────────────────────────────────────────────────

def detectar_temas_del_dia() -> list[dict]:
    """
    Combina todas las fuentes y devuelve los 5 mejores temas del día
    con score de relevancia para el Profesor Gato.
    
    Returns:
        Lista de dicts con {tema, fuente, score}
    """
    print("\n🔍 Detectando temas calientes del día...\n")
    candidatos = []

    # Google Trends
    trends = obtener_trends_google()
    for t in trends:
        candidatos.append({"tema": t, "fuente": "Google Trends", "score": 3})

    # NewsAPI
    noticias = obtener_noticias_educativas()
    for n in noticias:
        tema = f"{n['titulo']} ({n['fuente']})"
        candidatos.append({"tema": tema, "fuente": "NewsAPI", "score": 2})

    # Reddit
    reddit_temas = obtener_reddit_educativo()
    for t in reddit_temas:
        candidatos.append({"tema": t, "fuente": "Reddit", "score": 1})

    # Ordenar por score y devolver top 5
    candidatos_ordenados = sorted(candidatos, key=lambda x: x["score"], reverse=True)
    top5 = candidatos_ordenados[:5]

    print("\n📋 TOP 5 TEMAS DEL DÍA:")
    for i, c in enumerate(top5, 1):
        print(f"  {i}. [{c['fuente']}] {c['tema'][:80]}")

    return top5


if __name__ == "__main__":
    temas = detectar_temas_del_dia()
