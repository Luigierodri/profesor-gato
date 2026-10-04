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

# HERO CLIPS reutilizables del set GATO-CAST (video animado del Gato). Se usan a
# pantalla completa: 'gato_podcast' = el Gato hablando (ENTRADA); las reacciones se
# cortan en los momentos clave (campo "gato"). El audio del clip se descarta (va la voz).
HERO_DIR = BASE_DIR / "assets" / "hero"
GATO_TALK = HERO_DIR / "gato hablando set.mp4"
# pose del guion → clip de reacción (las que no tengan match usan 'enfasis' genérico)
_POSE_A_CLIP = {
    "indignado": "gato_react_enojado.mp4",
    "revela":    "gato_react_enfasis.mp4",
    "senala":    "gato_react_enfasis.mp4",
    "explica":   "gato_react_enfasis.mp4",
    "gancho":    "gato_react_enfasis.mp4",
    "dinero":    "gato_react_enojado.mp4",
    "piensa":    "gato_react_enfasis.mp4",
    "cierre":    "gato_react_enfasis.mp4",
}


def _gato_clip_para(pose: str):
    """Devuelve el HERO CLIP de reacción para una pose, si existe el archivo."""
    nombre = _POSE_A_CLIP.get(pose or "")
    if not nombre:
        return None
    p = HERO_DIR / nombre
    return p if p.exists() else None


_PP_DIR = HERO_DIR / "_pingpong"


def _hero_pingpong(src: Path) -> Path:
    """Devuelve una versión PALÍNDROMO (va y vuelve) del hero clip, cacheada. Así el
    loop es CONTINUO (el final empalma con el inicio) y el Gato no se 'reinicia'."""
    _PP_DIR.mkdir(parents=True, exist_ok=True)
    out = _PP_DIR / (Path(src).stem + "_pp.mp4")
    try:
        if out.exists() and out.stat().st_size > 10000:
            return out
        _run([FF, "-y", "-loglevel", "error", "-i", str(src),
              "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1:a=0[v]",
              "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "20",
              "-pix_fmt", "yuv420p", str(out)])
        return out if out.exists() else Path(src)
    except Exception:
        return Path(src)


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def _sfx_local(descripcion: str, out: Path) -> bool:
    """Resuelve un SFX de la DESPENSA local por keyword ($0, sin tocar la cuota de
    voz ni la red). Solo si hay match real; si no, el segmento va sin efecto."""
    try:
        from modules.sound_generator import _via_sfx_keyword
        return _via_sfx_keyword(descripcion or "", "", out)
    except Exception:
        return False


def _mezclar_sfx(voz: Path, sfx_src: Path, out: Path, dur: float):
    """Mezcla un acento de SFX al INICIO del segmento, por DEBAJO de la voz."""
    t = min(2.4, max(0.8, dur))
    _run([FF, "-y", "-loglevel", "error", "-i", str(voz), "-i", str(sfx_src),
          "-filter_complex",
          f"[1:a]atrim=0:{t:.2f},afade=t=out:st={max(0.1, t-0.4):.2f}:d=0.4,"
          f"volume=0.22[s];"
          "[0:a][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
          "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "3", str(out)])


def _concat_con_transiciones(clips, out: Path, work: Path, tipos) -> bool:
    """Une los clips con xfade (video) + acrossfade (audio). `tipos` = lista de
    (transicion, dur) por frontera (len = n-1). Devuelve True si lo logró; si no,
    False (el caller cae a concat seco para no romper el render)."""
    try:
        n = len(clips)
        if n < 2:
            return False
        durs = [_dur(c) for c in clips]
        if any(d <= 0 for d in durs):
            return False
        fg = []
        for i in range(n):
            fg.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H},fps=30,format=yuv420p,setsar=1,settb=AVTB[v{i}]")
            fg.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                      f"asettb=AVTB[a{i}]")
        cur_v, cur_a, acc = "[v0]", "[a0]", durs[0]
        for i in range(1, n):
            trans, T = tipos[i - 1]
            T = min(T, durs[i] - 0.05, durs[i - 1] - 0.05, acc - 0.05)
            if T <= 0.05:
                trans, T = "fade", 0.1
            off = max(0.0, acc - T)
            ov, oa = f"[vv{i}]", f"[aa{i}]"
            fg.append(f"{cur_v}[v{i}]xfade=transition={trans}:duration={T:.3f}:"
                      f"offset={off:.3f}{ov}")
            fg.append(f"{cur_a}[a{i}]acrossfade=d={T:.3f}:c1=tri:c2=tri{oa}")
            cur_v, cur_a, acc = ov, oa, acc + durs[i] - T
        fgfile = work / "transiciones_fg.txt"
        fgfile.write_text(";\n".join(fg), encoding="utf-8")
        cmd = [FF, "-y", "-loglevel", "error"]
        for c in clips:
            cmd += ["-i", str(c)]
        cmd += ["-filter_complex_script", str(fgfile), "-map", cur_v, "-map", cur_a,
                "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", str(out)]
        _run(cmd)
        return out.exists() and _dur(out) > 0
    except Exception as e:
        log.warning(f"  transiciones omitidas ({e}) — corte seco")
        return False


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


def _titulo_card(titulo: str, out_png: Path):
    """Tarjeta de TÍTULO (fondo cálido degradado + 'PROFESOR GATO presenta' + título
    grande dorado con resplandor). Se usa justo tras el cold open, con un golpe (SFX)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    img = Image.new("RGB", (W, H), (7, 7, 7))
    # degradado radial cálido desde arriba-izquierda
    grad = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grad)
    cx, cy, rmax = int(W * 0.30), int(H * 0.22), int(W * 0.95)
    for r in range(rmax, 0, -6):
        a = int(70 * (1 - r / rmax))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
    luz = Image.new("RGB", (W, H), (120, 86, 40))
    img = Image.composite(luz, img, grad)

    def _f(px, bold=True):
        for fp in (["C:/Windows/Fonts/ariblk.ttf"] if bold else []) + \
                  ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, px)
        return ImageFont.load_default()

    d = ImageDraw.Draw(img)
    oro, oro_glow, blanco = (242, 197, 106), (248, 222, 150), (238, 232, 220)

    # kicker
    kick = "P R O F E S O R   G A T O   P R E S E N T A"
    fk = _f(34, bold=False)
    wk = d.textbbox((0, 0), kick, font=fk)[2]
    d.text(((W - wk) // 2, int(H * 0.30)), kick, font=fk, fill=oro)

    # título grande (ajusta tamaño para que quepa; envuelve a 2 líneas si hace falta)
    titulo = (titulo or "").strip().upper()
    size = 118
    fT = _f(size)
    while d.textbbox((0, 0), titulo, font=fT)[2] > W * 0.84 and size > 52:
        size -= 6
        fT = _f(size)
    # envolver en 2 líneas si aún es muy ancho
    lineas = [titulo]
    if d.textbbox((0, 0), titulo, font=fT)[2] > W * 0.84:
        palabras = titulo.split()
        mid = len(palabras) // 2
        lineas = [" ".join(palabras[:mid]), " ".join(palabras[mid:])]
    y = int(H * 0.42)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdz = ImageDraw.Draw(glow)
    for ln in lineas:
        w = d.textbbox((0, 0), ln, font=fT)[2]
        gdz.text(((W - w) // 2, y), ln, font=fT, fill=oro_glow + (255,))
        y += int(size * 1.12)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.10))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(img)
    y = int(H * 0.42)
    for ln in lineas:
        w = d.textbbox((0, 0), ln, font=fT)[2]
        d.text(((W - w) // 2, y), ln, font=fT, fill=oro,
               stroke_width=max(2, size // 30), stroke_fill=(22, 16, 8))
        y += int(size * 1.12)

    # filo dorado bajo el título
    d.rectangle([int(W * 0.40), y + 14, int(W * 0.60), y + 20], fill=oro)
    img.save(out_png)


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

    # La tarjeta de título lleva un GOLPE (el "pum" cuando sube la música).
    if (seg.get("visual") or {}).get("tipo") == "titulo" and not seg.get("sfx"):
        seg["sfx"] = "thunder"

    # SFX del segmento (acento al inicio, por debajo de la voz). $0, despensa local.
    audio_use = audio
    sfx_desc = seg.get("sfx")
    if sfx_desc:
        sfx_src = work / f"x{idx:03d}.mp3"
        if _sfx_local(str(sfx_desc), sfx_src):
            mix = work / f"am{idx:03d}.mp3"
            try:
                _mezclar_sfx(audio, sfx_src, mix, _dur(audio))
                audio_use = mix
            except Exception as e:
                log.warning(f"  sfx seg {idx} omitido: {e}")

    clip = work / f"c{idx:03d}.mp4"
    visual = seg.get("visual") or {}
    tipo = visual.get("tipo")
    # HERO CLIP del Gato a pantalla completa: la ENTRADA (gato_podcast) o un CORTE
    # a reacción cuando el segmento lo pide (campo "gato"). El audio del clip se descarta.
    hero_clip = None
    if tipo == "gato_podcast" and GATO_TALK.exists():
        hero_clip = GATO_TALK
    elif tipo != "titulo" and seg.get("gato"):
        hero_clip = _gato_clip_para(seg.get("gato"))
    usou_hero = False

    if hero_clip:
        # loop ping-pong (va y vuelve) para que sea CONTINUO, sin "reinicio" visible
        _video_a_duracion(_hero_pingpong(Path(hero_clip)), d, clip)
        usou_hero = True
    elif tipo == "titulo":
        card = work / f"titulo_{idx:03d}.png"
        _titulo_card(visual.get("query") or texto, card)
        movimiento.foto_a_clip(str(card), str(clip), dur=d, movimiento="zoom_in", w=W, h=H)
    elif visual.get("tipo") == "grafica" and seg.get("datos"):
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
    # (Si ya se usó un HERO CLIP a pantalla completa, NO va además el sprite.)
    gato_pose = seg.get("gato")
    if (not usou_hero) and tipo not in ("titulo", "gato_podcast") and gato_pose in GATO_POSES:
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
        _run([FF, "-y", "-loglevel", "error", "-i", str(clip), "-i", str(audio_use), "-i", str(key),
              "-filter_complex", "[0:v][2:v]overlay=eof_action=pass[v]",
              "-map", "[v]", "-map", "1:a",
              "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-shortest", str(seg_out)])
    else:
        _run([FF, "-y", "-loglevel", "error", "-i", str(clip), "-i", str(audio_use),
              "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-shortest", str(seg_out)])
    return seg_out, audio_use, d, texto


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
    # Sabor musical por defecto si un segmento no trae "musica" propia.
    mus_default = (script.get("musica_global") or
                   "warm cinematic documentary score, strings and piano, emotional")
    clips, audios, textos, durs, flavors = [], [], [], [], []
    for i, seg in enumerate(segs, 1):
        seg["_tema_texto"] = tema_texto
        log.info(f"  Seg {i}/{len(segs)} [{seg.get('voz')}] {(seg.get('visual') or {}).get('tipo')}")
        c, a, d, t = _clip_segmento(seg, i, tema, work)
        clips.append(c); audios.append(a); textos.append(t)
        durs.append(_dur(c))
        flavors.append((seg.get("musica") or "").strip() or mus_default)

    # Transición por frontera: fundido a NEGRO al cambiar de capítulo (respira),
    # disolvencia corta dentro del mismo capítulo (fluido sin arrastrar).
    tipos = []
    for i in range(1, len(clips)):
        ca, cb = segs[i].get("capitulo", ""), segs[i - 1].get("capitulo", "")
        if ca and cb and ca != cb:
            tipos.append(("fadeblack", 0.45))
        else:
            tipos.append(("fade", 0.22))

    video = work / "video_concat.mp4"
    con_transiciones = _concat_con_transiciones(clips, video, work, tipos)
    if not con_transiciones:                       # fallback: corte seco (nunca rompe)
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{Path(c).as_posix()}'\n" for c in clips), encoding="utf-8")
        _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
              "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)])

    # voz completa para el karaoke: SIEMPRE del audio del video final, para que los
    # subtítulos queden alineados aunque las transiciones hayan acortado la línea.
    voz_full = work / "voz_full.mp3"
    try:
        _run([FF, "-y", "-loglevel", "error", "-i", str(video), "-vn",
              "-c:a", "libmp3lame", "-q:a", "3", str(voz_full)])
    except Exception:
        alst = work / "alist.txt"
        alst.write_text("".join(f"file '{Path(a).as_posix()}'\n" for a in audios), encoding="utf-8")
        _run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(alst),
              "-c:a", "libmp3lame", "-q:a", "3", str(voz_full)])
    guion_txt = work / "guion.txt"
    guion_txt.write_text(" ".join(textos), encoding="utf-8")

    actual = video
    # música de fondo a bajo volumen. Por defecto, TEMÁTICA por escena (cumbia/
    # aire colombiano cuando toca); MUSICA_TEMATICA=0 vuelve a la despensa de moods.
    if con_musica:
        try:
            mus = None
            if os.getenv("MUSICA_TEMATICA", "1") != "0":
                # fusiona bloques consecutivos del mismo sabor
                bloques = []
                for fl, du in zip(flavors, durs):
                    if bloques and bloques[-1][0] == fl:
                        bloques[-1] = (fl, bloques[-1][1] + du)
                    else:
                        bloques.append((fl, du))
                from modules.musica_tematica import cama_por_escena
                gen = os.getenv("MUSICA_TEMATICA_GEN", "1") != "0"
                log.info(f"  música temática: {len(bloques)} sabores — "
                         + " | ".join(f"{f[:24]}" for f, _ in bloques))
                mus = cama_por_escena(bloques, work, generar=gen)
            if not mus:
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
