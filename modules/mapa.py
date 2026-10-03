"""
mapa.py — Mapas ESTILIZADOS con identidad del canal (motor visual v2)
Proyecto: Profesor Gato

Genera un mapa 16:9 limpio que RESALTA un país/región en dorado sobre un fondo slate,
con el resto del mundo atenuado — estilo "Un Mundo Inmenso". Sin GIS pesado: solo
matplotlib + un GeoJSON del mundo (Natural Earth 110m, cacheado en assets/geo/).

Uso:  generar_mapa("Colombia", "salida.png")  -> ruta (o None si no encuentra el país)
"""
import json
import logging
import math
import unicodedata
from pathlib import Path

log = logging.getLogger("mapa")

BASE_DIR = Path(__file__).parent.parent
GEOJSON  = BASE_DIR / "assets" / "geo" / "world_110m.geojson"

# Paleta de identidad del canal.
_BG      = "#141c26"   # slate oscuro (fondo)
_OTROS   = "#2b3a4d"   # países atenuados
_BORDE   = "#141c26"   # borde sutil entre países
_GOLD    = "#E9C46A"   # país resaltado (dorado del canal)
_GOLD_HL = "#F6DC97"   # contorno del resaltado
_TEXTO   = "#F6DC97"

# Nombres en español comunes → como vienen en el GeoJSON (inglés).
_ALIAS = {
    "estados unidos": "United States of America", "eeuu": "United States of America",
    "reino unido": "United Kingdom", "inglaterra": "United Kingdom",
    "alemania": "Germany", "japon": "Japan", "brasil": "Brazil",
    "espana": "Spain", "francia": "France", "italia": "Italy",
    "mexico": "Mexico", "paises bajos": "Netherlands", "rusia": "Russia",
    "corea del sur": "South Korea", "corea del norte": "North Korea",
    "china": "China", "india": "India", "egipto": "Egypt", "grecia": "Greece",
    "turquia": "Turkey", "suecia": "Sweden", "suiza": "Switzerland",
    "sudafrica": "South Africa", "arabia saudita": "Saudi Arabia",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()
    return s


def _cargar():
    return json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]


def _buscar_pais(features, pais: str):
    objetivo = _ALIAS.get(_norm(pais), pais)
    objn = _norm(objetivo)
    campos = ("NAME", "NAME_ES", "NAME_LONG", "ADMIN", "SOVEREIGNT", "BRK_NAME")
    # match exacto primero, luego "contiene"
    for exacto in (True, False):
        for ft in features:
            p = ft["properties"]
            for c in campos:
                v = _norm(p.get(c, ""))
                if v and ((exacto and v == objn) or (not exacto and objn in v)):
                    return ft
    return None


def _anillos(geom):
    """Lista de anillos exteriores [(lons, lats), ...] para Polygon/MultiPolygon."""
    t, coords = geom["type"], geom["coordinates"]
    polis = coords if t == "MultiPolygon" else [coords]
    out = []
    for poli in polis:
        ext = poli[0]  # anillo exterior (ignoramos huecos a esta escala)
        xs = [c[0] for c in ext]; ys = [c[1] for c in ext]
        out.append((xs, ys))
    return out


def generar_mapa(pais: str, out_path, w: int = 1920, h: int = 1080) -> str | None:
    if not GEOJSON.exists():
        log.warning(f"  [mapa] falta {GEOJSON}")
        return None
    features = _cargar()
    objetivo = _buscar_pais(features, pais)
    if objetivo is None:
        log.warning(f"  [mapa] país no encontrado: '{pais}'")
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    from matplotlib.collections import PatchCollection

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor(_BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor(_BG); ax.axis("off")

    # bbox del país objetivo (para encuadrar con contexto)
    tx, ty = [], []
    patches_otros, patches_obj = [], []
    for ft in features:
        es_obj = ft is objetivo
        for xs, ys in _anillos(ft["geometry"]):
            poly = MplPoly(list(zip(xs, ys)), closed=True)
            (patches_obj if es_obj else patches_otros).append(poly)
            if es_obj:
                tx += xs; ty += ys

    ax.add_collection(PatchCollection(patches_otros, facecolor=_OTROS,
                                      edgecolor=_BORDE, linewidths=0.5, zorder=1))
    ax.add_collection(PatchCollection(patches_obj, facecolor=_GOLD,
                                      edgecolor=_GOLD_HL, linewidths=2.2, zorder=3))

    cx, cy = (min(tx) + max(tx)) / 2, (min(ty) + max(ty)) / 2
    span = max(max(tx) - min(tx), max(ty) - min(ty)) * 2.4 + 6  # contexto alrededor
    yhalf = span / 2
    xhalf = yhalf * (w / h)
    ax.set_xlim(cx - xhalf, cx + xhalf)
    ax.set_ylim(cy - yhalf, cy + yhalf)
    # corrige la distorsión lon/lat según latitud (si no, los países salen "aplastados")
    ax.set_aspect(1.0 / max(0.25, math.cos(math.radians(cy))))

    nombre = objetivo["properties"].get("NAME_ES") or objetivo["properties"].get("NAME") or pais
    ax.text(cx, max(ty) + yhalf * 0.10, nombre.upper(), color=_TEXTO, ha="center",
            va="bottom", fontsize=42, fontweight="bold", zorder=4,
            family="DejaVu Sans")

    fig.savefig(out_path, facecolor=_BG, dpi=100)
    plt.close(fig)
    log.info(f"  [mapa] {nombre} → {out_path.name}")
    return str(out_path)


if __name__ == "__main__":
    import sys
    pais = sys.argv[1] if len(sys.argv) > 1 else "Colombia"
    out = sys.argv[2] if len(sys.argv) > 2 else "tmp/mapa_demo.png"
    print(generar_mapa(pais, out))
