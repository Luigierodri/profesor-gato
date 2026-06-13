"""Ad-hoc: publica el LARGO de economía del Mundial (MP4 ya generado).
Receta de largos: usa el log essay_*.json (título + descripción + capítulos) y
sube el MP4 existente con publisher.subir_a_youtube. NO regenera (a diferencia de
run_essay --publish). Comentario CTA propio del tema (no el genérico de 7am).
Modo:  python publicar_largo_mundial.py [dry]
"""
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from publisher import subir_a_youtube

DRY = len(sys.argv) > 1 and sys.argv[1].lower() == "dry"
LOG = Path("logs/essay_20260612_181031.json")

d = json.loads(LOG.read_text(encoding="utf-8"))
ruta = Path(d["ruta_video"])
assert ruta.exists(), f"No existe el MP4: {ruta}"

metadata = {
    "titulo": d["titulo"][:100],
    "descripcion": d["descripcion"],
    "tags": ["Mundial 2026", "FIFA", "economia", "Mexico", "futbol",
             "ProfesorGato", "boletos Mundial", "negocio FIFA", "finanzas"],
    "tema": "el negocio del Mundial 2026",
}

res = subir_a_youtube(ruta, metadata, dry_run=DRY)

if DRY:
    print("\n[DRY] Título:", metadata["titulo"])
    print("[DRY] --- DESCRIPCIÓN ---\n" + metadata["descripcion"])
    sys.exit(0)

if res.get("_youtube"):
    yt, vid = res["_youtube"], res["video_id"]
    cta = ("⚽ La FIFA generará 11,000 millones de dólares con el Mundial 2026. "
           "México es el ÚNICO de los tres anfitriones que la exentó de impuestos "
           "(ISR, IVA, IEPS). Y el boleto más barato del partido inaugural cuesta "
           "más de DOS salarios mínimos.\n\n"
           "¿Irías a un partido a ese precio, o lo ves desde tu casa? Cuéntame 👇\n\n"
           "🐱 Aquí desarmamos una trampa del dinero cada semana. Suscríbete.")
    try:
        resp = yt.commentThreads().insert(part="snippet", body={"snippet": {
            "videoId": vid, "topLevelComment": {"snippet": {"textOriginal": cta}}}}).execute()
        print(f"  Comentario CTA publicado (id={resp['id']})")
    except Exception as e:
        print(f"  ⚠ No se pudo comentar: {e}")

print("URL:", res["url"])
