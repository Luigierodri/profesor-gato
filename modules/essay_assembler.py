"""
essay_assembler.py — Ensamble del VIDEO-ENSAYO LARGO (Profesor Gato)

HORIZONTAL 16:9 (1920x1080), 8-10 min. NUEVO y SEPARADO del video_assembler.py
de los Shorts (que es 9:16 y NO se toca). Esqueleto portado del essay_assembler
de Partida Guardada (probado en 7 largos); lo propio de Profesor Gato:

  - Fondo por segmento = imagen IA pixel art 16:9 con Ken Burns (no hay footage).
  - PERSONAJE del speaker (Gato/Bastet, PNG con pose) en la esquina inferior derecha.
  - TARJETA DE DATOS (la pieza estrella): si el segmento trae `dato`, el fondo se
    oscurece y se quema el número GRANDE dorado + comparación + fuente.
  - Subtítulos exactos (tiempos de ElevenLabs) con color por speaker.
  - Tarjetas de INTRO (título), CAPÍTULO y OUTRO; música Lyria por capítulo;
    pista de voz CONTINUA (concat PCM + micro-fades = sin clicks).
"""

import ffmpeg
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

log = logging.getLogger("essay_assembler")

BASE_DIR   = Path(__file__).parent.parent
VIDEOS_DIR = BASE_DIR / "videos_largos"          # carpeta APARTE de los Shorts
CHAR_DIR   = BASE_DIR / "images" / "personajes"
CHAR_PNGS_RAIZ = {
    "gato":   BASE_DIR / "images" / "profesor_gato_fondo_negro.png",
    "bastet": BASE_DIR / "images" / "bastet_fondo_negro.png",
}
POSES_VALIDAS = {
    "gato":   {"gancho", "explica", "revela", "cierre",
               "senala", "indignado", "piensa", "dinero"},
    "bastet": {"sorpresa", "pregunta", "preocupada", "eureka",
               "senala", "indignada", "asombrada", "triste"},
}

W, H, FPS = 1920, 1080, 30
MUSIC_VOLUME = 0.12
SUB_WORDS    = 4
CARD_DUR     = 2.6
INTRO_DUR    = 4.0
OUTRO_DUR    = 4.5
CHAR_W       = 470            # ~24% del ancho — personaje en esquina, no estorba

# Colores ASS (&HAABBGGRR sin alpha): dorado de marca y blanco.
GOLD  = "&H006AC5F2"          # RGB (242,197,106)
WHITE = "&H00FFFFFF"
BASTET_SUB = "&H00D6E8FF"     # blanco cálido para los subtítulos de Bastet


def resolver_char_png(speaker: str, pose: str = None) -> Path:
    """PNG del personaje según pose; cae al PNG raíz si la pose no existe."""
    speaker = speaker if speaker in POSES_VALIDAS else "gato"
    if pose and pose in POSES_VALIDAS[speaker]:
        p = CHAR_DIR / speaker / f"{speaker}_{pose}.png"
        if p.exists():
            return p
    return CHAR_PNGS_RAIZ.get(speaker, CHAR_PNGS_RAIZ["gato"])


def _ass_safe(t: str) -> str:
    """Quita llaves (abren bloques de override en ASS) y normaliza espacios."""
    return " ".join((t or "").replace("{", "").replace("}", "").split())


class EssayAssembler:

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg_essay_"))

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dur(self, p: Path) -> float:
        return float(ffmpeg.probe(str(p))["format"]["duration"])

    # ── Subtítulos (ASS) ──────────────────────────────────────────────────
    def _ts(self, t):
        h = int(t // 3600); m = int((t % 3600) // 60)
        s = int(t % 60);    cs = int((t - int(t)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _ass_subs(self, palabras: list[dict], nombre: str, speaker: str) -> Path:
        """Subtítulos de UN segmento; color según speaker (se distingue el dúo)."""
        ass = self.tmp / nombre
        color = BASTET_SUB if speaker == "bastet" else WHITE
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Arial,46,{color},&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,3,1,2,160,160,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for i in range(0, len(palabras), SUB_WORDS):
            chunk = palabras[i:i + SUB_WORDS]
            txt = _ass_safe(" ".join(w["w"] for w in chunk))
            lines.append(f"Dialogue: 0,{self._ts(float(chunk[0]['start']))},"
                         f"{self._ts(float(chunk[-1]['end']))},Sub,,0,0,0,,{txt}")
        ass.write_text("\n".join(lines), encoding="utf-8")
        return ass

    def _ass_datacard(self, dato: dict, dur: float, nombre: str) -> Path:
        """TARJETA DE DATOS: cifra GRANDE dorada + comparación + fuente."""
        ass = self.tmp / nombre
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cifra,Arial Black,150,{GOLD},&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,4,2,5,80,80,0,1
Style: Ctx,Arial,58,{WHITE},&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,3,1,5,160,160,0,1
Style: Src,Arial,30,&H00AAAAAA,&H000000FF,&H00000000,&H00000000,0,1,0,0,100,100,1,0,1,2,0,5,160,160,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        end = self._ts(dur)
        cifra    = _ass_safe(dato.get("cifra", ""))
        contexto = _ass_safe(dato.get("contexto", ""))
        fuente   = _ass_safe(dato.get("fuente", ""))
        lines = [header]
        lines.append(f"Dialogue: 0,0:00:00.20,{end},Cifra,,0,0,0,,"
                     f"{{\\an5\\pos({W//2},{H//2-130})\\fad(280,250)}}{cifra}")
        if contexto:
            lines.append(f"Dialogue: 0,0:00:00.45,{end},Ctx,,0,0,0,,"
                         f"{{\\an5\\pos({W//2},{H//2+30})\\fad(280,250)}}{contexto}")
        if fuente:
            lines.append(f"Dialogue: 0,0:00:00.45,{end},Src,,0,0,0,,"
                         f"{{\\an5\\pos({W//2},{H//2+115})\\fad(280,250)}}{fuente}")
        ass.write_text("\n".join(lines), encoding="utf-8")
        return ass

    def _ass_card(self, titulo_grande: str, linea_chica: str, dur: float,
                  nombre: str) -> Path:
        """Tarjeta centrada: una línea grande + (opcional) una chica arriba."""
        ass = self.tmp / nombre
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,Arial,76,{WHITE},&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,5,120,120,0,1
Style: Small,Arial,40,{GOLD},&H000000FF,&H00000000,&H00000000,0,1,0,0,100,100,3,0,1,2,0,5,120,120,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        end = self._ts(dur)
        titulo_grande = _ass_safe(titulo_grande)
        linea_chica = _ass_safe(linea_chica)
        if linea_chica:
            lines.append(f"Dialogue: 0,0:00:00.00,{end},Small,,0,0,0,,"
                         f"{{\\an5\\pos({W//2},{H//2-70})\\fad(300,300)}}{linea_chica.upper()}")
            lines.append(f"Dialogue: 0,0:00:00.00,{end},Big,,0,0,0,,"
                         f"{{\\an5\\pos({W//2},{H//2+20})\\fad(300,300)}}{titulo_grande}")
        else:
            lines.append(f"Dialogue: 0,0:00:00.00,{end},Big,,0,0,0,,"
                         f"{{\\an5\\fad(350,350)}}{titulo_grande}")
        ass.write_text("\n".join(lines), encoding="utf-8")
        return ass

    def _quemar(self, video_in: Path, ass: Path, out: Path):
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_in.resolve()),
             "-vf", f"subtitles={ass.name}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-preset", "veryfast", "-crf", "21", "-an", str(out.resolve())],
            capture_output=True, cwd=str(self.tmp))
        if r.returncode != 0:
            raise RuntimeError(f"subs error:\n{r.stderr.decode(errors='replace')[-600:]}")

    # ── Clip de un segmento (Ken Burns + personaje + dato + subs + voz) ────
    def _clip_segmento(self, b: dict) -> Path:
        dur = self.dur(Path(b["ruta_audio"]))
        n = b["numero"]
        es_dato = bool(b.get("dato"))

        # 1) Fondo: Ken Burns sobre la imagen 16:9 (mismo patrón de los Shorts).
        bg = (
            ffmpeg.input(str(b["ruta_imagen"]), loop=1, framerate=FPS, t=dur)
            .filter("scale", 8000, -1)
            .filter("zoompan",
                    z="min(zoom+0.0012,1.07)",
                    x="iw/2-(iw/zoom/2)", y="ih/2-(ih/zoom/2)",
                    d=int(dur * FPS), s=f"{W}x{H}", fps=FPS)
            .filter("setpts", "PTS-STARTPTS")
        )
        # Tarjeta de datos: el fondo se oscurece para que el número MANDE.
        if es_dato:
            bg = bg.filter("drawbox", c="black@0.55", t="fill")

        # 2) Personaje del speaker (esquina inferior derecha, no tapa subtítulos).
        char_png = resolver_char_png(b.get("speaker", "gato"), b.get("pose"))
        if char_png.exists():
            char = (
                ffmpeg.input(str(char_png), loop=1, framerate=FPS, t=dur)
                .filter("scale", CHAR_W, -2)
                .filter("format", "rgba")
                .filter("setpts", "PTS-STARTPTS")
            )
            video = ffmpeg.overlay(bg, char, x="W-w-55", y="H-h", format="auto")
        else:
            video = bg

        base_v = self.tmp / f"seg_{n:03d}_v.mp4"
        (ffmpeg.output(video, str(base_v), vcodec="libx264", pix_fmt="yuv420p",
                       r=FPS, t=dur, preset="veryfast", crf=21)
         .overwrite_output().run(quiet=True))

        # 3) Tarjeta de datos quemada (cifra + comparación + fuente).
        cur = base_v
        if es_dato:
            ass_d = self._ass_datacard(b["dato"], dur, f"seg_{n:03d}_dato.ass")
            con_dato = self.tmp / f"seg_{n:03d}_dv.mp4"
            self._quemar(cur, ass_d, con_dato)
            cur = con_dato

        # 4) Subtítulos exactos del segmento.
        palabras = b.get("palabras") or []
        if palabras:
            ass = self._ass_subs(palabras, f"seg_{n:03d}.ass", b.get("speaker", "gato"))
            sub_v = self.tmp / f"seg_{n:03d}_sv.mp4"
            self._quemar(cur, ass, sub_v)
            cur = sub_v

        # 5) Une video + voz.
        out = self.tmp / f"seg_{n:03d}.mp4"
        (ffmpeg.output(ffmpeg.input(str(cur)).video,
                       ffmpeg.input(str(b["ruta_audio"])).audio, str(out),
                       vcodec="libx264", acodec="aac", pix_fmt="yuv420p",
                       r=FPS, ar=44100, t=dur, preset="veryfast", crf=21)
         .overwrite_output().run(quiet=True))
        return out

    @staticmethod
    def _norm_card(t: str) -> str:
        """Equilibra signos ¿?/¡! en tarjetas para que se vean serias."""
        t = " ".join((t or "").split())
        if t.endswith("?") and "¿" not in t:
            t = "¿" + t
        if t.endswith("!") and "¡" not in t:
            t = "¡" + t
        return t

    # ── Cortinillas de marca (fondo PIL slate+dorado + personajes) ────────
    def _paw(self, d, cx: int, cy: int, s: float, color):
        """Huellita de gato: almohadilla + 3 deditos. `s` = escala (~1.0 = 22px)."""
        pad_w, pad_h = 22 * s, 16 * s
        d.ellipse([cx - pad_w / 2, cy - pad_h / 2, cx + pad_w / 2, cy + pad_h / 2],
                  fill=color)
        toe = 7 * s
        for dx, dy in ((-11 * s, -13 * s), (0, -17 * s), (11 * s, -13 * s)):
            d.ellipse([cx + dx - toe / 2, cy + dy - toe / 2,
                       cx + dx + toe / 2, cy + dy + toe / 2], fill=color)

    def _letterspaced(self, d, cx: int, y: int, texto: str, font, fill, extra: int = 10):
        """Texto centrado con letter-spacing (sello de marca)."""
        widths = [d.textlength(c, font=font) for c in texto]
        total = sum(widths) + extra * (len(texto) - 1)
        x = cx - total / 2
        for c, cw in zip(texto, widths):
            d.text((x, y), c, font=font, fill=fill)
            x += cw + extra

    def _pegar_char(self, img, speaker: str, pose: str, alto: int,
                    x: int = None, lado: str = "der", margen: int = 110):
        """Pega un personaje (PNG pose) anclado al piso interior de la cortinilla."""
        from PIL import Image as _Img
        p = resolver_char_png(speaker, pose)
        if not Path(p).exists():
            return
        ch = _Img.open(p).convert("RGBA")
        esc = alto / ch.height
        ch = ch.resize((int(ch.width * esc), alto), _Img.LANCZOS)
        y = H - 44 - ch.height
        if x is None:
            x = (W - margen - ch.width) if lado == "der" else margen
        img.alpha_composite(ch, (x, y))

    def _cortinilla_png(self, tipo: str, titulo_grande: str, linea_chica: str,
                        nombre: str, numero: int = None) -> Path:
        """Fondo de cortinilla 1920x1080 con la identidad del canal (slate+dorado,
        sello PROFESOR GATO con huellitas, personajes según el tipo)."""
        from PIL import Image as _Img, ImageDraw as _Draw
        from modules.data_chart import _font, _wrap, BG, GOLD, GOLD_SOFT, INK, INK_SOFT

        img = _Img.new("RGBA", (W, H), BG + (255,))
        d = _Draw.Draw(img)

        # Marco doble dorado (fino afuera, tenue adentro) = sello de "capítulo de libro"
        d.rectangle([26, 26, W - 26, H - 26], outline=GOLD, width=2)
        d.rectangle([38, 38, W - 38, H - 38], outline=GOLD_SOFT, width=1)

        # Sello superior: huellita · PROFESOR GATO · huellita
        f_marca = _font(30, bold=True)
        self._letterspaced(d, W // 2, 66, "PROFESOR GATO", f_marca, GOLD, extra=12)
        marca_w = sum(d.textlength(c, font=f_marca) for c in "PROFESOR GATO") + 12 * 12
        self._paw(d, int(W / 2 - marca_w / 2 - 48), 88, 1.0, GOLD)
        self._paw(d, int(W / 2 + marca_w / 2 + 48), 88, 1.0, GOLD)

        cx = W // 2
        if tipo == "intro":
            # Título del video + firma; el dúo flanquea
            f_tit = _font(84, bold=True)
            lineas = _wrap(d, titulo_grande, f_tit, W - 760)[:3]
            y = H // 2 - 60 - (len(lineas) - 1) * 52
            for ln in lineas:
                d.text((cx - d.textlength(ln, font=f_tit) / 2, y), ln, font=f_tit, fill=INK)
                y += 104
            d.rectangle([cx - 120, y + 26, cx + 120, y + 30], fill=GOLD)
            self._letterspaced(d, cx, y + 56, (linea_chica or "UN ENSAYO DE ECONOMÍA").upper(),
                               _font(34), GOLD, extra=8)
            self._pegar_char(img, "bastet", "pregunta", 500, lado="izq")
            self._pegar_char(img, "gato", "gancho", 520, lado="der")

        elif tipo == "reflexion":
            self._letterspaced(d, cx, H // 2 - 150, "PARA CERRAR", _font(38), GOLD, extra=10)
            f_tit = _font(78, bold=True)
            lineas = _wrap(d, titulo_grande, f_tit, W - 820)[:2]
            y = H // 2 - 60
            for ln in lineas:
                d.text((cx - d.textlength(ln, font=f_tit) / 2, y), ln, font=f_tit, fill=INK)
                y += 96
            self._paw(d, cx, y + 60, 1.3, GOLD_SOFT)
            self._pegar_char(img, "gato", "piensa", 540, lado="der")

        elif tipo == "outro":
            f_tit = _font(80, bold=True)
            d.text((cx - d.textlength(titulo_grande, font=f_tit) / 2, H // 2 - 110),
                   titulo_grande, font=f_tit, fill=INK)
            self._letterspaced(d, cx, H // 2 + 16, (linea_chica or "").upper(),
                               _font(40, bold=True), GOLD, extra=8)
            self._paw(d, cx - 170, H // 2 + 110, 1.2, GOLD_SOFT)
            self._paw(d, cx,       H // 2 + 124, 1.2, GOLD)
            self._paw(d, cx + 170, H // 2 + 110, 1.2, GOLD_SOFT)
            self._pegar_char(img, "bastet", "eureka", 470, lado="izq")
            self._pegar_char(img, "gato", "cierre", 500, lado="der")

        else:  # capítulo numerado
            etiqueta = f"CAPÍTULO {numero}" if numero else "CAPÍTULO"
            f_eti = _font(38)
            eti_w = d.textlength(etiqueta, font=f_eti) + 9 * (len(etiqueta) - 1)
            self._letterspaced(d, cx, H // 2 - 148, etiqueta, f_eti, GOLD, extra=9)
            # Reglitas doradas a los lados de la etiqueta
            ry = H // 2 - 128
            d.rectangle([cx - eti_w / 2 - 170, ry, cx - eti_w / 2 - 40, ry + 3], fill=GOLD_SOFT)
            d.rectangle([cx + eti_w / 2 + 40, ry, cx + eti_w / 2 + 170, ry + 3], fill=GOLD_SOFT)
            f_tit = _font(82, bold=True)
            lineas = _wrap(d, titulo_grande, f_tit, W - 560)[:2]
            y = H // 2 - 58
            for ln in lineas:
                d.text((cx - d.textlength(ln, font=f_tit) / 2, y), ln, font=f_tit, fill=INK)
                y += 100
            self._paw(d, cx, y + 64, 1.3, GOLD_SOFT)

        out_png = self.tmp / f"{nombre}.png"
        img.convert("RGB").save(out_png)
        return out_png

    # ── Tarjetas / cortinillas (fondo de marca + zoom sutil + silencio) ────
    def _tarjeta(self, titulo_grande: str, linea_chica: str, dur: float,
                 nombre: str, tipo: str = "capitulo", numero: int = None) -> Path:
        titulo_grande = self._norm_card(titulo_grande)
        linea_chica = self._norm_card(linea_chica)
        png = self._cortinilla_png(tipo, titulo_grande, linea_chica,
                                   f"{nombre}_bg", numero=numero)
        out = self.tmp / f"{nombre}.mp4"
        fade_d = 0.35
        video = (
            ffmpeg.input(str(png), loop=1, framerate=FPS, t=dur)
            .filter("scale", 2400, -1)
            .filter("zoompan", z="min(zoom+0.0006,1.025)",
                    x="iw/2-(iw/zoom/2)", y="ih/2-(ih/zoom/2)",
                    d=int(dur * FPS), s=f"{W}x{H}", fps=FPS)
            .filter("fade", type="in", start_time=0, duration=fade_d)
            .filter("fade", type="out", start_time=max(0.0, dur - fade_d), duration=fade_d)
            .filter("setpts", "PTS-STARTPTS")
        )
        sil = ffmpeg.input("anullsrc=r=44100:cl=stereo", f="lavfi", t=dur).audio
        (ffmpeg.output(video, sil, str(out),
                       vcodec="libx264", acodec="aac", pix_fmt="yuv420p",
                       r=FPS, ar=44100, t=dur, preset="veryfast", crf=21)
         .overwrite_output().run(quiet=True))
        return out

    def _concat_video(self, piezas: list[Path], out: Path):
        """Concatena SOLO video; el audio se reconstruye aparte (sin clicks)."""
        lista = self.tmp / "concat.txt"
        with open(lista, "w", encoding="utf-8") as f:
            for p in piezas:
                f.write(f"file '{p.resolve().as_posix()}'\n")
        (ffmpeg.input(str(lista), format="concat", safe=0)
         .output(str(out), an=None, vcodec="libx264", pix_fmt="yuv420p", r=FPS)
         .overwrite_output().run(quiet=True))

    def _audio_continuo(self, specs: list[tuple], out: Path):
        """UNA pista de voz continua (concat PCM, micro-fades 6ms) = sin clicks.
        specs = [("voice", mp3, dur) | ("sil", dur), ...] en orden de pieza."""
        inputs, filt, labels = [], [], []
        fd = 0.006
        for i, sp in enumerate(specs):
            if sp[0] == "voice":
                dur = sp[2]
                inputs += ["-i", str(sp[1])]
            else:
                dur = sp[1]
                inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i",
                           "anullsrc=r=44100:cl=stereo"]
            fo = max(0.0, dur - fd)
            filt.append(f"[{i}:a]aresample=44100,"
                        f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                        f"afade=t=in:st=0:d={fd},afade=t=out:st={fo:.3f}:d={fd}[a{i}]")
            labels.append(f"[a{i}]")
        fc = ";".join(filt) + ";" + "".join(labels) + f"concat=n={len(specs)}:v=0:a=1[out]"
        r = subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
                            "-map", "[out]", str(out)], capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"audio continuo error:\n{r.stderr.decode(errors='replace')[-500:]}")

    def _construir_musica(self, spans: list[tuple], out: Path) -> bool:
        """Pista de música del largo total: un bed por capítulo, loopeado a su
        duración con fades; capítulos sin bed quedan en silencio."""
        if not any(bed for _, bed in spans):
            return False
        inputs, filt, labels = [], [], []
        for i, (dur, bed) in enumerate(spans):
            if bed and Path(bed).exists():
                inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", str(bed)]
                fade = min(1.2, dur / 4) if dur > 0 else 0
                filt.append(
                    f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"volume={MUSIC_VOLUME},afade=t=in:st=0:d={fade:.2f},"
                    f"afade=t=out:st={max(0,dur-fade):.2f}:d={fade:.2f}[a{i}]")
            else:
                inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i",
                           "anullsrc=r=44100:cl=stereo"]
                filt.append(f"[{i}:a]aresample=44100,"
                            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
            labels.append(f"[a{i}]")
        fc = ";".join(filt) + ";" + "".join(labels) + f"concat=n={len(spans)}:v=0:a=1[out]"
        r = subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
                            "-map", "[out]", str(out)], capture_output=True)
        if r.returncode != 0:
            log.warning(f"  música falló: {r.stderr.decode(errors='replace')[-200:]}")
            return False
        return True

    def _mux_final(self, video_body: Path, voz_full: Path, music_track: Path, out: Path):
        """Voz continua + música (largo total) sobre el video sin re-encodear."""
        total = self.dur(video_body)
        def _run(con_musica: bool) -> bool:
            if con_musica:
                cadena = "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]"
                ins = ["-i", str(video_body), "-i", str(voz_full), "-i", str(music_track)]
            else:
                cadena = "[1:a]anull[a]"
                ins = ["-i", str(video_body), "-i", str(voz_full)]
            r = subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex", cadena,
                                "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                                "-c:a", "aac", "-movflags", "+faststart",
                                "-t", f"{total:.2f}", str(out)], capture_output=True)
            if r.returncode != 0:
                log.warning(f"  mux ({'música' if con_musica else 'sin música'}) falló: "
                            f"{r.stderr.decode(errors='replace')[-200:]}")
            return r.returncode == 0
        hay = bool(music_track and Path(music_track).exists())
        if _run(hay): return
        _run(False)

    # ── Orquestador ───────────────────────────────────────────────────────
    def ensamblar(self, bloques: list[dict], titulo: str,
                  musica_por_capitulo: dict = None,
                  output_name: str = None) -> tuple[Path, list[dict]]:
        """bloques = [{numero, ruta_audio, ruta_imagen, palabras, speaker, pose,
                       dato, capitulo}, ...]"""
        if output_name is None:
            output_name = f"essay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = VIDEOS_DIR / f"{output_name}.mp4"

        log.info("=" * 55)
        log.info(f"ENSAMBLE ENSAYO PG (16:9) — {len(bloques)} segmentos")
        log.info("=" * 55)
        try:
            piezas, specs, capitulos = [], [], []
            timeline = 0.0
            prev_cap = None
            num_cap = 0                      # numeración visible (la intro no cuenta)
            intro_pendiente = False
            _es_reflexion = lambda c: any(k in c.lower() for k in
                                          ("reflexi", "final", "cierre", "conclusi", "moraleja"))

            for i, b in enumerate(bloques):
                cap = b.get("capitulo", "") or ""
                if cap != prev_cap:
                    capitulos.append({"titulo": cap or "Capítulo", "t": timeline})
                    cards = []
                    if prev_cap is None:
                        # COLD OPEN (retención, 5 jul 2026): el gancho de la Introducción
                        # entra EN FRÍO al segundo 0; la cortinilla de título se pospone
                        # al primer cambio de capítulo (cuando el gancho ya retuvo).
                        intro_pendiente = True
                    else:
                        if intro_pendiente:
                            cards.append(self._tarjeta(titulo, "Un ensayo de economía",
                                                       INTRO_DUR, "card_intro", tipo="intro"))
                            intro_pendiente = False
                        if _es_reflexion(cap):
                            cards.append(self._tarjeta(cap, "", CARD_DUR + 0.6,
                                                       f"card_cap_{i:03d}", tipo="reflexion"))
                        else:
                            num_cap += 1
                            cards.append(self._tarjeta(cap, "", CARD_DUR, f"card_cap_{i:03d}",
                                                       tipo="capitulo", numero=num_cap))
                    for card in cards:
                        d = self.dur(card)
                        piezas.append(card); specs.append(("sil", d)); timeline += d
                    if cards:
                        log.info(f"  🃏 cortinilla: {cap or titulo}")
                    else:
                        log.info(f"  🎬 cold open: '{cap}' entra sin cortinilla (gancho directo)")

                try:
                    clip = self._clip_segmento(b)
                except ffmpeg.Error as e:
                    err = (e.stderr or b"").decode(errors="replace")[-600:]
                    log.error(f"  ✗ ffmpeg en segmento {b['numero']} "
                              f"(imagen={b.get('ruta_imagen')}):\n{err}")
                    raise
                dseg = self.dur(clip)
                piezas.append(clip); specs.append(("voice", b["ruta_audio"], dseg))
                timeline += dseg
                if b.get("dato"):
                    log.info(f"  🔢 seg {b['numero']}: tarjeta de datos "
                             f"\"{b['dato'].get('cifra','')}\"")
                if (i + 1) % 5 == 0:
                    log.info(f"  ...segmento {i+1}/{len(bloques)} ({timeline:.0f}s)")
                prev_cap = cap

            outro = self._tarjeta("¿Quieres más? Haz clic aquí",
                                  "Suscríbete · Profesor Gato", OUTRO_DUR,
                                  "card_outro", tipo="outro")
            piezas.append(outro); specs.append(("sil", self.dur(outro)))

            log.info(f"\n[concat] {len(piezas)} piezas (video) + pista de voz continua...")
            cuerpo = self.tmp / "cuerpo.mp4"
            self._concat_video(piezas, cuerpo)
            voz_full = self.tmp / "voz_full.wav"
            self._audio_continuo(specs, voz_full)
            total = self.dur(cuerpo)

            log.info("[música] construyendo pista variada por capítulo...")
            spans = []
            for i, c in enumerate(capitulos):
                ini = c["t"]
                fin = capitulos[i + 1]["t"] if i + 1 < len(capitulos) else total
                bed = (musica_por_capitulo or {}).get(c["titulo"])
                spans.append((max(0.1, fin - ini), bed))
            music_track = self.tmp / "music_full.wav"
            hay_mus = self._construir_musica(spans, music_track)

            log.info("[mux] voz continua + música...")
            self._mux_final(cuerpo, voz_full, music_track if hay_mus else None, output_path)

            dur_final = self.dur(output_path)
            size_mb = output_path.stat().st_size / 1024 / 1024
            log.info(f"\n🎬 LISTO: videos_largos/{output_path.name} "
                     f"({size_mb:.1f} MB, {dur_final/60:.1f} min)")
            return output_path, capitulos
        finally:
            self.cleanup()
