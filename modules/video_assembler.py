"""
video_assembler.py — Módulo 5: Ensamble Final del Video
Proyecto: Profesor Gato 🐱

ARQUITECTURA v4 — Pipeline por Paneles:
  - Cada panel = imagen + audio sincronizados → clip con Ken Burns
  - Clips concatenados → video base
  - Música lofi de fondo mezclada
  - Subtítulos quemados estilo TikTok
  - Output: videos/ en formato 9:16 (1080x1920)
"""

import ffmpeg
import logging
import tempfile
import shutil
import random
from pathlib import Path
from datetime import datetime
from faster_whisper import WhisperModel

log = logging.getLogger("video_assembler")
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

BASE_DIR   = Path(__file__).parent.parent
ASSETS_DIR = BASE_DIR / "assets"
MUSIC_DIR  = ASSETS_DIR / "music"
VIDEOS_DIR = BASE_DIR / "videos"

VIDEO_WIDTH          = 1080
VIDEO_HEIGHT         = 1920
VIDEO_FPS            = 30
MUSIC_VOLUME         = 0.10
EFFECTS_VOLUME       = 0.15
NARRATION_VOLUME     = 1.0
FADE_DURATION        = 0.5
SUBTITLE_FONTSIZE    = 58
SUBTITLE_WORDS_PER_CHUNK = 4

# Assets oficiales de personajes (PNG con fondo negro)
CHAR_PNGS = {
    "gato":   BASE_DIR / "images" / "profesor_gato_fondo_negro.png",
    "bastet": BASE_DIR / "images" / "bastet_fondo_negro.png",
}
CHAR_PNG_WIDTH = int(VIDEO_WIDTH * 0.45)  # 486px — ~45% del ancho


class VideoAssemblerV4:

    def __init__(self, musica_mood: str = "lofi"):
        self.tmp = Path(tempfile.mkdtemp(prefix="profgato_v4_"))
        self.musica_mood = musica_mood

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get_duration(self, p: Path) -> float:
        return float(ffmpeg.probe(str(p))["format"]["duration"])

    # ─────────────────────────────────────────────
    # PASO 1a: Clip con imagen real + overlay personaje
    # ─────────────────────────────────────────────

    def crear_clip_con_overlay(
        self,
        ruta_imagen: str,
        ruta_audio: str,
        numero: int,
        speaker: str = "gato",
        ruta_video: str = None,
    ) -> Path:
        """
        Crea el clip de panel con:
        - Fondo: clip Veo animado (o Ken Burns si no hay animación)
        - Overlay: asset PNG oficial del personaje (fondo negro removido vía colorkey),
                   posicionado en la parte inferior central del frame al 45% del ancho
        - Audio: narración del panel
        """
        duracion = self.get_duration(Path(ruta_audio))
        out      = self.tmp / f"clip_{numero:02d}.mp4"
        char_png = CHAR_PNGS.get(speaker, CHAR_PNGS["gato"])

        # Fondo: clip Veo o Ken Burns
        if ruta_video:
            clip_dur = self.get_duration(Path(ruta_video))
            base = (
                ffmpeg.input(str(ruta_video))
                .filter("scale", VIDEO_WIDTH, VIDEO_HEIGHT,
                        force_original_aspect_ratio="increase")
                .filter("crop", VIDEO_WIDTH, VIDEO_HEIGHT)
            )
            if clip_dur < duracion:
                base = base.filter(
                    "tpad", stop_mode="clone",
                    stop_duration=duracion - clip_dur
                )
            bg = (
                base
                .filter("trim", duration=duracion)
                .filter("setpts", "PTS-STARTPTS")
            )
        else:
            bg = (
                ffmpeg.input(str(ruta_imagen), loop=1, framerate=VIDEO_FPS, t=duracion)
                .filter("scale", 8000, -1)
                .filter("zoompan",
                        z="min(zoom+0.0015,1.08)",
                        x="iw/2-(iw/zoom/2)",
                        y="ih/2-(ih/zoom/2)",
                        d=int(duracion * VIDEO_FPS),
                        s=f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
                        fps=VIDEO_FPS)
                .filter("setpts", "PTS-STARTPTS")
            )

        # Personaje: PNG RGBA con fondo ya transparente (convertido por floodfill).
        # El canal alpha del PNG se usa directamente — sin keying ni geq.
        if char_png.exists():
            char = (
                ffmpeg.input(str(char_png), loop=1, framerate=VIDEO_FPS, t=duracion)
                .filter("scale", CHAR_PNG_WIDTH, -2)
                .filter("format", "rgba")
                .filter("setpts", "PTS-STARTPTS")
            )
            # x=(W-w)/2 → centrado horizontal; y=H-h-20 → pegado al borde inferior
            video = ffmpeg.overlay(bg, char, x="(W-w)/2", y="H-h-20", format="auto")
            log.info(f"  [{speaker.upper()}] overlay PNG: {char_png.name}")
        else:
            log.warning(f"  Asset PNG no encontrado: {char_png} — clip sin personaje")
            video = bg

        audio = ffmpeg.input(str(ruta_audio)).audio

        (
            ffmpeg.output(
                video, audio, str(out),
                vcodec="libx264", acodec="aac",
                pix_fmt="yuv420p", r=VIDEO_FPS,
                t=duracion, preset="ultrafast", crf=26,
            )
            .overwrite_output()
            .run(quiet=True)
        )

        modo = "Veo+overlay" if ruta_video else "KenBurns+overlay"
        log.info(f"  clip_{numero:02d}.mp4 ({duracion:.1f}s) [{modo}] [{speaker}]")
        return out

    # ─────────────────────────────────────────────
    # PASO 1b: Clip con imagen generada (gpt-image-2 + Kling)
    # ─────────────────────────────────────────────

    def crear_clip_panel(
        self,
        ruta_imagen: str,
        ruta_audio: str,
        numero: int,
        ruta_video: str = None,
    ) -> Path:
        """
        Une imagen/video + audio de un panel en un clip mp4.
        Si ruta_video está presente usa el clip animado (en loop hasta
        cubrir la duración del audio) y escala a 1080x1920.
        Si no, aplica el efecto Ken Burns sobre la imagen estática.
        """
        duracion = self.get_duration(Path(ruta_audio))
        out = self.tmp / f"clip_{numero:02d}.mp4"

        if ruta_video:
            # Clip animado escalado a 1080x1920; si el clip es más corto que el
            # audio, congela el último frame (tpad clone) en lugar de hacer loop.
            clip_dur = self.get_duration(Path(ruta_video))
            base = (
                ffmpeg.input(str(ruta_video))
                .filter("scale", VIDEO_WIDTH, VIDEO_HEIGHT,
                        force_original_aspect_ratio="increase")
                .filter("crop", VIDEO_WIDTH, VIDEO_HEIGHT)
            )
            if clip_dur < duracion:
                base = base.filter(
                    "tpad", stop_mode="clone",
                    stop_duration=duracion - clip_dur
                )
            video = (
                base
                .filter("trim", duration=duracion)
                .filter("setpts", "PTS-STARTPTS")
            )
            modo = "animado"
        else:
            # Fallback: Ken Burns desde imagen estática
            video = (
                ffmpeg.input(str(ruta_imagen), loop=1, framerate=VIDEO_FPS, t=duracion)
                .filter("scale", 8000, -1)
                .filter("zoompan",
                        z="min(zoom+0.0015,1.08)",
                        x="iw/2-(iw/zoom/2)",
                        y="ih/2-(ih/zoom/2)",
                        d=int(duracion * VIDEO_FPS),
                        s=f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
                        fps=VIDEO_FPS)
                .filter("setpts", "PTS-STARTPTS")
            )
            modo = "Ken Burns"

        audio = ffmpeg.input(str(ruta_audio)).audio

        (
            ffmpeg.output(
                video, audio, str(out),
                vcodec="libx264", acodec="aac",
                pix_fmt="yuv420p", r=VIDEO_FPS,
                t=duracion, preset="ultrafast", crf=26,
                shortest=None
            )
            .overwrite_output()
            .run(quiet=True)
        )

        log.info(f"  ✅ clip_{numero:02d}.mp4 ({duracion:.1f}s) [{modo}]")
        return out

    # ─────────────────────────────────────────────
    # PASO 2: Concatenar todos los clips
    # ─────────────────────────────────────────────

    def concatenar_clips(self, clips: list[Path]) -> Path:
        """Concatena todos los clips de paneles en un video continuo."""
        out = self.tmp / "video_base.mp4"
        lista = self.tmp / "clips_list.txt"

        with open(lista, "w", encoding="utf-8") as f:
            for clip in clips:
                f.write(f"file '{clip.resolve().as_posix()}'\n")

        (
            ffmpeg.input(str(lista), format="concat", safe=0)
            .output(str(out), vcodec="libx264", acodec="aac",
                    pix_fmt="yuv420p", r=VIDEO_FPS)
            .overwrite_output()
            .run(quiet=True)
        )

        duracion = self.get_duration(out)
        log.info(f"  ✅ Video base: {len(clips)} paneles, {duracion:.1f}s total")
        return out

    # ─────────────────────────────────────────────
    # PASO 3: Subtítulos
    # ─────────────────────────────────────────────

    def concatenar_audios(self, rutas_audio: list[str]) -> Path:
        """Une todos los audios de paneles en un solo mp3."""
        out = self.tmp / "audio_completo.mp3"
        lista = self.tmp / "audio_list.txt"

        with open(lista, "w", encoding="utf-8") as f:
            for ruta in rutas_audio:
                f.write(f"file '{Path(ruta).resolve().as_posix()}'\n")

        (
            ffmpeg.input(str(lista), format="concat", safe=0)
            .output(str(out), acodec="mp3", ar=44100)
            .overwrite_output()
            .run(quiet=True)
        )
        return out

    def transcribir(self, audio_path: Path) -> list[dict]:
        """Transcribe el audio y genera segmentos con timestamps."""
        log.info("  Transcribiendo para subtítulos...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(str(audio_path), language="es", word_timestamps=True)

        segments = []
        idx = 1
        for seg in segs:
            words = list(seg.words or [])
            if not words:
                segments.append({
                    "index": idx, "start": seg.start,
                    "end": seg.end, "text": seg.text.strip().upper()
                })
                idx += 1
                continue
            for i in range(0, len(words), SUBTITLE_WORDS_PER_CHUNK):
                chunk = words[i:i + SUBTITLE_WORDS_PER_CHUNK]
                segments.append({
                    "index": idx,
                    "start": chunk[0].start,
                    "end": chunk[-1].end,
                    "text": " ".join(w.word.strip() for w in chunk).upper()
                })
                idx += 1

        log.info(f"  ✅ {len(segments)} segmentos de subtítulos")
        return segments

    def generar_ass(self, segments: list[dict]) -> Path:
        """Genera archivo .ass de subtítulos estilo TikTok."""
        ass_path = self.tmp / "subtitles.ass"

        def ts(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            cs = int((t - int(t)) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,{SUBTITLE_FONTSIZE},&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,2,0,3,4,2,2,40,40,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for seg in segments:
            lines.append(
                f"Dialogue: 0,{ts(seg['start'])},{ts(seg['end'])},Default,,0,0,0,,{seg['text']}"
            )
        ass_path.write_text("\n".join(lines), encoding="utf-8")
        return ass_path

    def quemar_subtitulos(self, video: Path, ass: Path) -> Path:
        out = self.tmp / "subtitled.mp4"
        import subprocess
        # Run ffmpeg from self.tmp so the ASS path is just "subtitles.ass" —
        # no drive letter or backslashes that confuse ffmpeg's filter parser on Windows.
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video.resolve()),
            "-vf", f"subtitles={ass.name}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", str(VIDEO_FPS), "-preset", "ultrafast", "-crf", "26",
            "-an", str(out.resolve()),
        ]
        result = subprocess.run(cmd, capture_output=True, cwd=str(self.tmp))
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg subtitles error:\n{result.stderr.decode(errors='replace')}"
            )
        log.info("  ✅ Subtítulos quemados")
        return out

    # ─────────────────────────────────────────────
    # PASO 4: Música de fondo
    # ─────────────────────────────────────────────

    def mezclar_audio(self, audio_completo: Path, duracion: float,
                      musica_path: Path = None, lyria_path: Path = None) -> Path:
        """
        Mezcla 3 capas de audio:
          1. Narración (100%)
          2. Efectos de ambiente / musica_path (15%) — si está disponible
          3. Música: lyria_path si existe, sino track estático de assets/music/ (10%)

        lyria_path es música generada por Lyria 3 (contextual, única por video).
        musica_path es el efecto ambiental (batalla, laboratorio, etc.).
        """
        out = self.tmp / "audio_final.aac"

        narr = ffmpeg.input(str(audio_completo)).audio.filter("volume", NARRATION_VOLUME)

        # Capa 2: efectos ambientales (opcional)
        efectos = None
        if musica_path and musica_path.exists():
            log.info(f"  🔊 Ambiente: {musica_path.name}")
            efectos = (
                ffmpeg.input(str(musica_path), stream_loop=-1, t=duracion).audio
                .filter("volume", EFFECTS_VOLUME)
                .filter("afade", type="in", start_time=0, duration=FADE_DURATION)
                .filter("afade", type="out",
                        start_time=max(0, duracion - FADE_DURATION), duration=FADE_DURATION)
            )

        # Capa 3: música de fondo — Lyria 3 tiene prioridad; fallback tracks estáticos
        lofi = None
        _audio_exts = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

        if lyria_path and lyria_path.exists():
            log.info(f"  🎵 Música [Lyria 3]: {lyria_path.name}")
            lofi = (
                ffmpeg.input(str(lyria_path), stream_loop=-1, t=duracion).audio
                .filter("volume", MUSIC_VOLUME)
                .filter("afade", type="in", start_time=0, duration=FADE_DURATION)
                .filter("afade", type="out",
                        start_time=max(0, duracion - FADE_DURATION), duration=FADE_DURATION)
            )
        else:
            music_files = []
            if MUSIC_DIR.exists():
                mood_dir = MUSIC_DIR / (self.musica_mood or "lofi")
                buscar_en = mood_dir if mood_dir.is_dir() else MUSIC_DIR
                music_files = [
                    f for f in buscar_en.rglob("*")
                    if f.is_file() and f.suffix.lower() in _audio_exts
                    and "generated" not in f.parts  # no reciclar música generada de otros videos
                ]
                if not music_files:
                    music_files = [
                        f for f in MUSIC_DIR.rglob("*")
                        if f.is_file() and f.suffix.lower() in _audio_exts
                        and "generated" not in f.parts
                    ]
            if music_files:
                track = random.choice(music_files)
                log.info(f"  🎵 Música [{self.musica_mood}] (estática): {track.name}")
                lofi = (
                    ffmpeg.input(str(track), stream_loop=-1, t=duracion).audio
                    .filter("volume", MUSIC_VOLUME)
                    .filter("afade", type="in", start_time=0, duration=FADE_DURATION)
                    .filter("afade", type="out",
                            start_time=max(0, duracion - FADE_DURATION), duration=FADE_DURATION)
                )

        capas = [narr] + [c for c in [efectos, lofi] if c is not None]

        if len(capas) == 1:
            log.warning("  Sin música ni efectos disponibles")
            (narr.output(str(out), acodec="aac", ar=44100)
             .overwrite_output().run(quiet=True))
            return out

        (
            ffmpeg.filter(capas, "amix", inputs=len(capas),
                          duration="first", dropout_transition=2, normalize=0)
            .output(str(out), acodec="aac", ar=44100, t=duracion)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info(f"  ✅ Audio mezclado ({len(capas)} capas)")
        return out

    # ─────────────────────────────────────────────
    # PASO 5: Merge final
    # ─────────────────────────────────────────────

    def merge_final(self, video: Path, audio: Path, output_path: Path):
        duracion = self.get_duration(video)
        (
            ffmpeg.input(str(video)).video
            # Forzar resolución 1080x1920 (9:16) — escalar si el clip no es exacto
            .filter("scale", VIDEO_WIDTH, VIDEO_HEIGHT,
                    force_original_aspect_ratio="disable")
            .filter("fade", type="in", start_time=0, duration=0.3)
            .filter("fade", type="out",
                    start_time=max(0, duracion - FADE_DURATION), duration=FADE_DURATION)
            .output(
                ffmpeg.input(str(audio)).audio, str(output_path),
                vcodec="libx264", acodec="aac", pix_fmt="yuv420p",
                r=VIDEO_FPS, ar=44100, movflags="+faststart", shortest=None
            )
            .overwrite_output()
            .run(quiet=True)
        )
        log.info(f"  Resolución forzada: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")

    # ─────────────────────────────────────────────
    # ORQUESTADOR PRINCIPAL
    # ─────────────────────────────────────────────

    def ensamblar(self, paneles: list[dict], output_name: str = None,
                  musica_path: Path = None, lyria_path: Path = None) -> Path:
        """
        Ensambla el video final a partir de los paneles.

        Args:
            paneles:     Lista de dicts con 'ruta_imagen', 'ruta_audio', 'numero'
            output_name: Nombre del archivo de salida (sin extensión)
            musica_path: Path al efecto ambiental (batalla, laboratorio, etc.)
            lyria_path:  Path a la música generada por Lyria 3 (reemplaza tracks estáticos)
        """
        if output_name is None:
            output_name = f"profgato_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = VIDEOS_DIR / f"{output_name}.mp4"

        log.info("=" * 55)
        log.info(f"ENSAMBLE v4 — {len(paneles)} paneles")
        log.info("=" * 55)

        try:
            log.info("\n[1/5] Creando clips por panel...")
            clips = []
            for panel in paneles:
                clip = self.crear_clip_panel(
                    panel["ruta_imagen"],
                    panel["ruta_audio"],
                    panel["numero"],
                    ruta_video=panel.get("ruta_video"),
                )
                clips.append(clip)

            log.info("\n[2/5] Concatenando clips...")
            video_base = self.concatenar_clips(clips)
            duracion_total = self.get_duration(video_base)

            log.info("\n[3/5] Generando subtítulos...")
            rutas_audio = [p["ruta_audio"] for p in paneles]
            audio_completo = self.concatenar_audios(rutas_audio)
            segments = self.transcribir(audio_completo)
            ass_file = self.generar_ass(segments)
            video_subtitulado = self.quemar_subtitulos(video_base, ass_file)

            log.info("\n[4/5] Mezclando audio...")
            audio_final = self.mezclar_audio(audio_completo, duracion_total,
                                             musica_path=musica_path,
                                             lyria_path=lyria_path)

            log.info("\n[5/5] Generando video final...")
            self.merge_final(video_subtitulado, audio_final, output_path)

            size_mb = output_path.stat().st_size / 1024 / 1024
            log.info(f"\n🎬 LISTO: videos/{output_path.name} ({size_mb:.1f} MB)")
            log.info(f"   Duración: {duracion_total:.1f}s")
            return output_path

        except Exception as e:
            log.error(f"Error en ensamble: {e}", exc_info=True)
            raise
        finally:
            self.cleanup()


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 4:
        print("Uso: python -m modules.video_assembler <json> <carpeta_audios> <carpeta_imagenes>")
        print("Ejemplo:")
        print("  python -m modules.video_assembler \\")
        print("    logs/comic_La_Tragedia_del_Mar_de_Aral.json \\")
        print("    audio/La_Tragedia_del_Mar_de_Aral_20260517_132408 \\")
        print("    images/La_Tragedia_del_Mar_de_Aral_20260517_140012")
        sys.exit(1)

    ruta_json     = sys.argv[1]
    carpeta_audio = Path(sys.argv[2])
    carpeta_imgs  = Path(sys.argv[3])

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos_comic = json.load(f)

    paneles = []
    for panel in datos_comic["paneles"]:
        n = panel["numero"]
        paneles.append({
            "numero":      n,
            "ruta_audio":  str(carpeta_audio / f"panel_{n:02d}.mp3"),
            "ruta_imagen": str(carpeta_imgs  / f"panel_{n:02d}.png"),
        })

    assembler = VideoAssemblerV4()
    video = assembler.ensamblar(paneles)
    print(f"\n✅ Video final: {video}")