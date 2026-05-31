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
import xml.etree.ElementTree as ET
import requests
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import anthropic
from config import NEWS_API_KEY, ANTHROPIC_API_KEY, CLAUDE_MODEL
from modules import topic_history

# Códigos de país para el RSS de Google Trends (no usa pytrends — funciona desde CI)
_GEOS_LATAM = {"MX": "méxico", "AR": "argentina", "CO": "colombia", "CL": "chile", "PE": "perú"}


# ─── GOOGLE TRENDS RSS ────────────────────────────────────────────────────────

def obtener_trends_google(paises: dict = None, limite: int = 10) -> list[dict]:
    """
    Lee el RSS público de Google Trends por país.
    No requiere autenticación ni cookies — funciona desde GitHub Actions.
    URL: https://trends.google.com/trending/rss?geo=MX
    """
    if paises is None:
        paises = _GEOS_LATAM
    resultados = {}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProfesorGato/1.0)"}
    for geo, nombre in paises.items():
        try:
            url = f"https://trends.google.com/trending/rss?geo={geo}"
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                titulo = (item.findtext("title") or "").strip()
                if titulo and len(titulo) > 3:
                    resultados[titulo] = resultados.get(titulo, 0) + 1
        except Exception as e:
            print(f"  Google Trends RSS ({geo}) error: {e}")
    temas = [
        {"tema": t, "fuente": "Google Trends RSS", "score": 3 + v, "paises": v}
        for t, v in sorted(resultados.items(), key=lambda x: -x[1])
    ]
    print(f"  Google Trends RSS: {len(temas)} temas de {len(paises)} países")
    return temas[:limite]


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
          "evento":           str,   # tag canónico del evento (snake_case)
          "razon":            str,   # por qué tiene tracción hoy
        }
    """
    if not tendencias:
        return {"angulo_educativo": None, "trend_conectado": None, "evento": "", "razon": "sin tendencias"}

    lista_str = "\n".join(
        f"- [{c['fuente']}] {c['tema']} (score {c['score']})"
        for c in tendencias[:10]
    )

    # ── Memoria de temas: evitar repetir ángulos y saturar eventos ──────────────
    angulos_prev   = topic_history.angulos_recientes()
    eventos_tope   = topic_history.eventos_en_tope()
    eventos_vistos = topic_history.eventos_conocidos()

    bloque_memoria = ""
    if angulos_prev:
        lista_ang = "\n".join(f"  - {a}" for a in angulos_prev[-15:])
        bloque_memoria += (
            "\nÁNGULOS YA PUBLICADOS RECIENTEMENTE — está PROHIBIDO repetirlos o "
            "hacer uno casi igual. Si reutilizas el mismo evento, el ángulo DEBE ser "
            f"claramente distinto (otro enfoque, otra arista):\n{lista_ang}\n"
        )
    if eventos_tope:
        bloque_memoria += (
            "\nEVENTOS SATURADOS — ya alcanzaron su tope de videos en los últimos "
            f"{topic_history.VENTANA_CAP_DIAS} días. NO elijas un ángulo de estos eventos, "
            f"escoge OTRO tema distinto aunque esté menos arriba en trending:\n  "
            + ", ".join(eventos_tope) + "\n"
        )
    if eventos_vistos:
        bloque_memoria += (
            "\nTAGS DE EVENTO YA EN USO — si tu ángulo pertenece a uno de estos eventos, "
            "reutiliza EXACTAMENTE el mismo tag en el campo 'evento':\n  "
            + ", ".join(eventos_vistos) + "\n"
        )

    prompt = f"""Eres el productor del canal educativo "Profesor Gato" en YouTube Shorts (México/LATAM).

El canal explica: historia, cultura, sociedad, economía, ciencia, fenómenos urbanos.
NO hace videos de noticias directas — explica el PORQUÉ y el trasfondo de lo que pasa.

Trending hoy en México/LATAM:
{lista_str}
{bloque_memoria}
Elige UN tema trending y formula el ÁNGULO EDUCATIVO más potente, RESPETANDO las reglas
de arriba (no repetir ángulos, no usar eventos saturados, variar el enfoque).
El ángulo debe conectarse con algo que hoy está en boca de todos y explicar su trasfondo
histórico, cultural, científico o económico. Si TODO lo trending ya está agotado o saturado,
propón un tema educativo atemporal y potente que NO esté en la lista de ángulos ya publicados.

Ejemplos de conversión trend → ángulo educativo:
- Trend: "Colombia elecciones mañana" → Ángulo: "¿Por qué Colombia ha cambiado tantas veces de constitución?"
- Trend: "CDMX hundimiento" → Ángulo: "¿Por qué se está hundiendo la Ciudad de México?"
- Trend: "Mundial 2026" → varía el ángulo entre videos: "El Azteca, único estadio con 3 Mundiales" /
  "La derrama económica que deja un Mundial" / "Los problemas sociales detrás de organizar un Mundial"
- Trend: "Taylor Swift tour" → Ángulo: "¿Por qué los conciertos se volvieron tan caros?"

El campo "evento" es un tag corto en snake_case que agrupa videos del mismo suceso
(ej: "mundial_2026", "elecciones_colombia_2026", "hundimiento_cdmx"). Reutiliza el mismo
tag para el mismo evento. Si es un tema atemporal, usa un tag temático (ej: "historia_roma").

Responde SOLO JSON válido, sin markdown:
{{
  "angulo_educativo": "la pregunta o afirmación del video en español",
  "trend_conectado": "el trending topic que usas como gancho de relevancia",
  "evento": "tag_en_snake_case",
  "razon": "en una frase, por qué este ángulo tiene tracción hoy"
}}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    resultado = json.loads(raw)
    resultado.setdefault("evento", "")
    print(f"  Angulo educativo: {resultado['angulo_educativo']}")
    print(f"  Trend conectado:  {resultado.get('trend_conectado')}")
    print(f"  Evento (tag):     {resultado.get('evento')}")
    print(f"  Razon:            {resultado.get('razon', '')}")
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
