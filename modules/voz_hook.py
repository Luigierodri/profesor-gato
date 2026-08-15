"""
voz_hook.py — Masterización de voz OPCIONAL (EQ + compresión + -14 LUFS).

Gated por env MASTER_VOZ=1 (apagado por defecto). Usa SIEMPRE recortar=False:
solo mejora el sonido, NO recorta silencios → conserva la duración exacta, así los
timestamps de ElevenLabs (subtítulos) siguen alineados. Guarded: si falla, deja el
audio original intacto.

Uso:
    from modules.voz_hook import masterizar_si_activado
    masterizar_si_activado(ruta_mp3)     # in-place, solo si MASTER_VOZ=1
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("voz_hook")


def masterizar_si_activado(ruta_audio) -> str:
    ruta_audio = str(ruta_audio)
    if os.environ.get("MASTER_VOZ", "0") != "1":
        return ruta_audio
    if not ruta_audio or not os.path.exists(ruta_audio):
        return ruta_audio
    try:
        from modules.masterizar_voz import masterizar
    except Exception as e:
        log.warning(f"  masterizar_voz no disponible ({e}); voz sin masterizar")
        return ruta_audio
    tmp = str(Path(ruta_audio).with_suffix(".mast" + Path(ruta_audio).suffix))
    try:
        masterizar(ruta_audio, tmp, recortar=False)   # recortar=False = misma duración
        os.replace(tmp, ruta_audio)
        return ruta_audio
    except SystemExit as e:
        log.warning(f"  masterización abortó ({e}); voz sin masterizar")
    except Exception as e:
        log.warning(f"  masterización falló ({e}); voz sin masterizar")
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
    return ruta_audio
