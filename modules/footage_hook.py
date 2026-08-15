"""
footage_hook.py — Verificación/curado SEGURO de footage (verificar_footage).

Corre tras descargar un clip: detecta texto quemado (OCR), marcas de agua/HUD y
tarjetas de rating. Dos modos:
  - verificar (siempre): AVISA en el log si el clip trae basura. No toca el archivo.
  - curar (opt-in por argumento): recorta a las ventanas LIMPIAS (sobrescribe). Solo
    seguro donde el clip se loopea a una duración fija (ej. fondos de essay).

Reglas del canal: NUNCA romper el render. Si algo falla o no hay material limpio
suficiente, deja el clip ORIGINAL intacto. Gated por VERIFICAR_FOOTAGE (default ON).
El OCR necesita tesseract en el PATH (o TESSERACT_CMD); sin él degrada a overlay/negros.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("footage_hook")

MIN_LIMPIO_PARA_CURAR = 4.0     # si hay menos de esto limpio, NO recortar (evita over-trim)


def _config_tesseract():
    """Si TESSERACT_CMD está seteado, apúntalo; si no, se usa el del PATH."""
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = cmd
        except Exception:
            pass


def verificar_footage(clip_path, curar: bool = False, rapido: bool = False):
    """Verifica (y opcionalmente cura) un clip. Devuelve la ruta (curada u original).
    NUNCA lanza: si algo falla, devuelve el clip tal cual."""
    clip_path = str(clip_path)
    if os.environ.get("VERIFICAR_FOOTAGE", "1") != "1":
        return clip_path
    if not clip_path or not os.path.exists(clip_path):
        return clip_path

    _config_tesseract()
    try:
        from modules.verificar_footage import analizar, exportar_limpio
    except Exception as e:
        log.warning(f"  verificar_footage no disponible ({e}); footage sin verificar")
        return clip_path

    try:
        rep = analizar(clip_path, rapido=rapido)
    except Exception as e:
        log.warning(f"  análisis de footage falló ({e}); dejo el clip como está")
        return clip_path

    nombre = os.path.basename(clip_path)
    # Avisos (siempre)
    if rep.overlays:
        (x, y, w), etiqueta, frec = max(rep.overlays, key=lambda c: c[2])
        marca = f' "{etiqueta}"' if etiqueta else ""
        log.warning(f"  ⚠ footage '{nombre}': overlay fijo{marca} en {rep.zona_marca} "
                    f"({frec*100:.0f}% del clip)")
    if not rep.ventanas:
        log.warning(f"  ⚠ footage '{nombre}': SIN ventana limpia — conviene otra fuente")
        return clip_path

    hay_basura = rep.segundos_limpios < rep.duracion - 1.0
    if curar and hay_basura and rep.segundos_limpios >= MIN_LIMPIO_PARA_CURAR:
        tmp = str(Path(clip_path).with_suffix(".curado.mp4"))
        try:
            out = exportar_limpio(clip_path, rep, tmp)
            if out and os.path.exists(tmp):
                os.replace(tmp, clip_path)
                log.info(f"  ✓ footage '{nombre}' curado: {rep.segundos_limpios:.1f}s "
                         f"limpios de {rep.duracion:.1f}s")
        except Exception as e:
            log.warning(f"  curado de footage falló ({e}); dejo el clip original")
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    elif hay_basura:
        log.info(f"  footage '{nombre}': {rep.segundos_limpios:.1f}s limpios de "
                 f"{rep.duracion:.1f}s (sin curar)")
    return clip_path
