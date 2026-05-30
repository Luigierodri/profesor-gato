"""Verifica que cost_tracker funcione correctamente con datos de prueba."""
import sys, os
sys.path.insert(0, r"C:\Users\luigi\Desktop\profesor-gato")

from dotenv import load_dotenv
load_dotenv(r"C:\Users\luigi\Desktop\profesor-gato\.env")

from modules import cost_tracker

# Iniciar sesión
log_path = cost_tracker.init_session(
    tema="TEST — La Revolución Francesa",
    log_path=None  # usa tmp/cost_log.txt por defecto
)
print(f"Log en: {log_path}")

# Simular una corrida completa con datos ficticios

# Paso 2 — Claude script
cost_tracker.registrar_tokens(
    "claude-haiku-4-5-20251001",
    in_tok=3_842, out_tok=1_204,
    ctx="Script: La Revolución Francesa",
)

# Paso 4 — ElevenLabs ×6 paneles
for i in range(1, 7):
    speaker = "GATO" if i % 2 != 0 else "BASTET"
    chars = 280 + i * 15
    cost_tracker.registrar_voz(
        "eleven_multilingual_v2", n_chars=chars,
        ctx=f"Panel {i} [{speaker}]",
    )

# Paso 5 — Imagen 4 ×6 paneles
for i in range(1, 7):
    speaker = "gato" if i % 2 != 0 else "bastet"
    cost_tracker.registrar_imagen(
        "imagen-4.0-fast-generate-001", n=1,
        ctx=f"Panel {i} ({speaker})",
    )

# Paso 5.5 — Veo ×6 paneles (6s cada uno)
for i in range(1, 7):
    cost_tracker.registrar_video(
        "veo-3.1-lite-generate-preview", duracion_seg=6,
        ctx=f"Panel {i}",
    )

# Paso 5.9 — Lyria música (45s)
cost_tracker.registrar_audio(
    "lyria-002", duracion_seg=45.0,
    ctx="Mood: dramatico",
)

# Resumen final
resumen = cost_tracker.session_summary()

print("\n" + "═" * 50)
print("RESUMEN DE PRUEBA:")
for tipo, total in resumen["por_tipo"].items():
    print(f"  {tipo:<8}: ${total:.4f}")
print(f"  {'TOTAL':<8}: ${resumen['total_usd']:.4f}")
print(f"  Llamadas: {resumen['n_llamadas']}")
print(f"  Estimados: {resumen['tiene_estimados']}")
print("═" * 50)
print(f"\nVer detalle completo en: {resumen['log_path']}")
