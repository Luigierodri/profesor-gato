# -*- coding: utf-8 -*-
"""Ad-hoc: publica el LARGO 'economía que hereda el nuevo presidente de Colombia'
(MP4 ya generado, NO regenera). Título con MAYÚSCULAS. CTA no-partidista.
Modo:  python publicar_abelardo.py [dry]
"""
import sys, json, glob
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from publisher import subir_a_youtube

DRY = len(sys.argv) > 1 and sys.argv[1].lower() == "dry"

ruta = Path(sorted(glob.glob("videos_largos/20260807_193230_ESSAY_*.mp4"))[-1])
assert ruta.exists(), f"No existe el MP4: {ruta}"
script = json.loads(Path("audio/ESSAY_Qué_economía_hereda_el_nuevo_p_20260807_192541/script.json").read_text(encoding="utf-8"))

desc = (script.get("descripcion", "").strip() + "\n\n"
        "📊 Sin banderas ni bandos: solo los números que recibe cualquier gobierno que "
        "entra en 2026. Deuda, déficit, inflación, dólar y empleo, explicados claro.\n\n"
        "🐱 Cada semana desarmamos una trampa del dinero. Suscríbete.\n\n"
        "#Colombia #Economía #ProfesorGato #Finanzas #DeLaEspriella #Deuda")

metadata = {
    "titulo": "¿Qué economía HEREDA el nuevo presidente de COLOMBIA?"[:100],
    "descripcion": desc,
    "tags": ["Colombia", "economia colombiana", "deuda publica", "deficit fiscal",
             "inflacion Colombia", "PIB Colombia", "De la Espriella", "presidente Colombia 2026",
             "dolar peso", "ProfesorGato", "finanzas", "empleo informalidad"],
    "tema": "economia que hereda el presidente de colombia",
}

res = subir_a_youtube(ruta, metadata, dry_run=DRY)

if DRY:
    print("\n[DRY] Título:", metadata["titulo"])
    print("[DRY] MP4:", ruta.name)
    print("[DRY] --- DESCRIPCIÓN ---\n" + metadata["descripcion"][:600])
    sys.exit(0)

if res.get("_youtube"):
    yt, vid = res["_youtube"], res["video_id"]
    cta = ("🇨🇴 Hoy Colombia estrena presidente número 61. Más allá del discurso, esta es "
           "la economía REAL que recibe: déficit por encima del 6% del PIB, una deuda que "
           "subió con fuerza en tres años, inflación arriba de la meta y la mitad del país "
           "trabajando en la informalidad.\n\n"
           "Sin decirte por quién votar: ¿cuál debería ser la prioridad número uno con "
           "esta herencia? 👇\n\n"
           "🐱 Economía sin bandos, cada semana. Suscríbete.")
    try:
        resp = yt.commentThreads().insert(part="snippet", body={"snippet": {
            "videoId": vid, "topLevelComment": {"snippet": {"textOriginal": cta}}}}).execute()
        print(f"  Comentario CTA publicado (id={resp['id']})")
    except Exception as e:
        print(f"  ⚠ No se pudo comentar: {e}")

print("URL:", res["url"])
