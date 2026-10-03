"""
ensamblador_narrador.py — EL INTEGRADOR del formato narrador (motor visual v2)
Proyecto: Profesor Gato

Toma un guion-narrador (ver prompts/system_prompt_narrador.txt) y arma el video:
  guion → por cada segmento: voz (paleta) + visual REAL (foto/footage/mapa/moneda/
  gráfica con selector_visual) + movimiento + palabra dorada → concat → subtítulos
  karaoke → música de la despensa. Devuelve la ruta del .mp4.

Reusa: aplicar_tema, selector_visual, movimiento, render_grafica, VOCES, num_es,
subtitulos_karaoke, music_generator. Todo lo construido hasta aquí, junto.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path

import requests

from config import ELEVENLABS_API_KEY, VOCES
from modules import selector_visual, movimiento
from modules.graficas_animadas import aplicar_tema, render_grafica
from modules.num_es import normalizar_numeros_es
from modules.pronunciacion import corregir_pronunciacion

# El Profesor Gato SIEMPRE habla con esta voz (su voz real/cercana). Nunca se mezcla.
VOZ_GATO = "luigi"

log = logging.getLogger("ensamblador_narrador")

BASE_DIR = Path(__file__).parent.parent
_FFDIR = (r"C:\Users\luigi\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin")
FF = shutil.which("ffmpeg") or os.path.join(_FFDIR, "ffmpeg.exe")
FP = shutil.which("ffprobe") or os.path.join(_FFDIR, "ffprobe.exe")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"
W, H = 1920, 1080
GATO_DIR = BASE_DIR / "images" / "personajes" / "gato"
GATO_POSES = {"gancho", "explica", "revela", "cierre", "senala", "indignado", "piensa", "dinero"}


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def _dur(path) -> float:
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _tts(texto: str, voz: str, out: Path):
    v = VOCES.get(voz, VOCES["narrador"])
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{v['voice_id']}",
        json={"text": corregir_pronunciacion(normalizar_numeros_es(texto)), "model_id": v["model"],
              "voice_settings": v["settings"]},
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"}, timeout=180)
    r.raise_for_status()
    out.write_bytes(r.content)


def _video_a_duracion(src: Path, dur: float, out: Path):
    """Loopea/corta un clip (footage o gráfica) a `dur`, cubre 16:9, sin audio."""
    _run([FF, "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(src),
          "-t", f"{dur:.3f}",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p",
          "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(out)])


def _grafica_de_datos(datos: dict, out_mp4: Path, tema: str):
    """Renderiza una gráfica de barras (animada) desde los `datos` del segmento."""
    vals = datos.get("valores", [])
    spec = {
        "forma": "barras", "tema": tema,
        "titulo": datos.get("titulo", ""), "unidad": datos.get("unidad", ""),
        "datos": [[v.get("label", ""), v.get("valor", 0)] for v in vals],
        "fuente": datos.get("fuente", ""),
    }
    render_grafica(spec, str(out_mp4))


def _clip_segmento(seg: dict, idx: int, tema: str, work: Path) -> tuple:
    """Devuelve (clip_con_audio, audio, dur, texto). El clip ya trae la palabra dorada."""
    texto = seg.get("narracion", "").strip()
    voz = seg.get("voz", "narrador")
    # Si el Gato APARECE en este segmento, habla SÍ o SÍ con su voz (nunca se mezcla).
    if seg.get("gato") in GATO_POSES:
        voz = VOZ_GATO
    audio = work / f"a{idx:03d}.mp3"
    _tts(texto, voz, audio)
    d = _dur(audio) + 0.35

    clip = work / f"c{idx:03d}.mp4"
    visual = seg.get("visual") or {}
    if visual.get("tipo") == "grafica" and seg.get("datos"):
        g = work / f"g{idx:03d}.mp4"
        _grafica_de_datos(seg["datos"], g, tema)
        _video_a_duracion(g, d, clip)
    else:
        vr = selector_visual.obtener_visual(visual, seg.get("_tema_texto", ""), work, idx)
        if vr["ruta"] and vr["es_video"]:
            _video_a_duracion(Path(vr["ruta"]), d, clip)
        elif vr["ruta"]:
            movimiento.foto_a_clip(vr["ruta"], str(clip), dur=d,
                                   movimiento=vr.get("movimiento", "zoom_in"), w=W, h=H)
        else:   # sin visual: negro
            _run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                  f"color=c=0x070707:s={W}x{H}:d={d:.3f}", "-c:v", "libx264", str(clip)])

    # El PROFESOR GATO aparece recortado en una pose (si el segmento lo pide),
    # deslizándose desde la derecha. Ocasional — lo marca el guion con "gato".
    gato_pose = seg.get("gato")
    if gato_pose in GATO_POSES:
        sprite = GATO_DIR / f"gato_{gato_pose}.png"
        if sprite.exists():
            clip_g = work / f"cg{idx:03d}.mp4"
            _run([FF, "-y", "-loglevel", "error", "-i", str(clip), "-i", str(sprite),
                  "-filter_complex",
                  "[1]scale=-1:640[g];"
                  "[0][g]overlay=x='if(lt(t,0.45),W-(w*(t/0.45)),W-w-20)':y=H-h+30[v]",
                  "-map", "[v]", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(clip_g)])
            clip = clip_g

    # mux voz + palabra CINÉTICA (letra por letra + resplandor), solo si hay clave
    seg_out = work / f"s{idx:03d}.mp4"
    clave = (seg.get("visual") or {}).get("clave")
    if clave:
        from modules.tipografia import render_palabra_cinetica
        key = work / f"k{idx:03d}.mov"
        render_palabra_cinetica(str(clave), key, dur=min(max(d - 0.3, 1.2), 2.6))
        _run([FF, "-y", "-loglevel", "error", "-i", str(clip), "-i", str(audio), "-i", str(key),
              "-filter_complex", "[0:v][2:v]overlay=eof_action=pass[v]",
              "-map", "[v]", "-map", "1:a",
              "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-shortest", str(seg_out)])
    else:
        _run([FF, "-y", "-loglevel", "error", "-i", str(clip), "-i", str(audio),
              "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-shortest", str(seg_out)])
    return seg_out, audio, d, texto


def armar_video(script: dict, out_path, tema: str = None, work: Path = None,
                con_karaoke: bool = True, con_musica: bool = True) -> str:
    """Arma el video completo del guion-narrador. Devuelve la ruta del .mp4."""
    tema = tema or script.get("tema", "negro_oro")
    aplicar_tema(tema)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = Path(work) if work else (BASE_DIR / "tmp" / "ensamblador")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    tema_texto = script.get("titulo", "")
    segs = script.get("segmentos", [])
    clips, audios, textos = [], [], []
    for i, seg in enumerate(segs, 1):
        seg["_tema_texto"] = tema_texto
        log.info(f"  Seg {i}/{len(segs)} [{seg.get('voz')}] {(seg.get('visual') or {}).get('tipo')}")
        c, a, d, t = _clip_segmento(seg, i, tema, work)
        clips.append(c); audios.append(a); textos.append(t)

    # concat de clips (mismos parámetros)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{Path(c).as_posix()}'\n" for c in clips), encoding="utf-8")
    video = work / "video_concat.mp4"
    _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
          "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)])

    # voz completa (para el karaoke) + guion de texto
    voz_full = work / "voz_full.mp3"
    alst = work / "alist.txt"
    alst.write_text("".join(f"file '{Path(a).as_posix()}'\n" for a in audios), encoding="utf-8")
    _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(alst),
          "-c:a", "libmp3lame", "-q:a", "3", str(voz_full)])
    guion_txt = work / "guion.txt"
    guion_txt.write_text(" ".join(textos), encoding="utf-8")

    actual = video
    # música de fondo (despensa/Lyria) a bajo volumen
    if con_musica:
        try:
            from modules.music_generator import seleccionar_musica
            total = _dur(video)
            mood = script.get("musica_mood", "ambient_misterioso")
            mus = seleccionar_musica(mood, tema_texto, total)
            if mus:
                con_mus = work / "con_musica.mp4"
                _run([FF, "-y", "-loglevel", "error", "-i", str(actual), "-stream_loop", "-1",
                      "-i", str(mus),
                      "-filter_complex", "[1:a]volume=0.16[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                      "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(con_mus)])
                actual = con_mus
        except Exception as e:
            log.warning(f"  música omitida: {e}")

    # subtítulos karaoke (palabra activa dorada)
    if con_karaoke:
        try:
            from modules.subtitulos_karaoke import quemar_subtitulos, ESTILO_LARGO
            quemar_subtitulos(video_in=str(actual), audio_voz=str(voz_full),
                              video_out=str(out_path), estilo=ESTILO_LARGO,
                              guion=str(guion_txt))
            log.info(f"  ✓ {out_path.name} (con karaoke)")
            return str(out_path)
        except Exception as e:
            log.warning(f"  karaoke omitido ({e}) — se usa el video sin subtítulos")

    shutil.copy(actual, out_path)
    log.info(f"  ✓ {out_path.name}")
    return str(out_path)


if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        import truststore; truststore.inject_into_ssl()
    except Exception:
        pass
    with open(sys.argv[1], encoding="utf-8") as f:
        script = json.load(f)
    out = sys.argv[2] if len(sys.argv) > 2 else "tmp/narrador_demo.mp4"
    print(armar_video(script, out,
                      con_karaoke="--no-karaoke" not in sys.argv,
                      con_musica="--no-musica" not in sys.argv))
