"""
sonido_hook.py — Wrapper SEGURO de la capa de diseño de sonido (efectos_sonido).

Se engancha al final del render (después de video+voz, antes de publicar). Regla
del canal: NUNCA romper el render. Si el SFX falla o falta ffmpeg/pack, deja el
video original tal cual y sigue. Se puede desactivar con la env var SFX_OFF=1.

Uso:
    from modules.sonido_hook import aplicar_sonido_seguro
    aplicar_sonido_seguro(ruta_video, guion=texto_narracion)   # in-place
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("sonido_hook")


def aplicar_sonido_seguro(video, guion: str = "", marcas: dict | None = None,
                          musica: str | None = None):
    """Aplica la capa de sonido SOBRE el mismo archivo (in-place). Devuelve la
    ruta del video (con SFX si salió bien, sin tocar si algo falló)."""
    video = str(video)
    if os.environ.get("SFX_OFF") == "1":
        log.info("  SFX_OFF=1 — capa de sonido desactivada")
        return video
    if not video or not os.path.exists(video):
        return video

    try:
        from modules.efectos_sonido import aplicar_sonido
    except Exception:
        try:
            from efectos_sonido import aplicar_sonido       # por si se corre desde modules/
        except Exception as e:
            log.warning(f"  efectos_sonido no disponible ({e}); video sin SFX")
            return video

    tmp = str(Path(video).with_suffix(".sfx.mp4"))
    try:
        aplicar_sonido(video_in=video, video_out=tmp,
                       guion=(guion or None), musica=musica, marcas=marcas)
        os.replace(tmp, video)
        log.info("  ✓ capa de sonido aplicada")
        return video
    except SystemExit as e:
        # efectos_sonido usa sys.exit() si falta el pack; no queremos matar el pipeline
        log.warning(f"  capa de sonido abortó ({e}); dejo el video sin SFX")
    except Exception as e:
        log.warning(f"  capa de sonido falló ({e}); dejo el video sin SFX")
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
    return video
