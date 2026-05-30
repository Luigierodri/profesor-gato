"""
video_assembler.py — Módulo 5: Ensamble Final del Video
Proyecto: Profesor Gato 🐱

NUEVA ARQUITECTURA:
  - Fondo: imagen generada por DALL-E 3 (1024x1792 → escalado a 1080x1920)
  - Personaje: profesor_gato_fondo_negro.jpg recortado del negro (chroma key)
  - Audio: narración ElevenLabs + música lofi de fondo
  - Subtítulos: quemados con FFmpeg (palabras en chunks de 4)
  - Output: video 9:16 vertical listo para TikTok/Reels/Shorts

Resultado visual:
  ┌─────────────────┐
  │                 │
  │  FONDO DALL-E   │  ← imagen 16-bit del tema
  │   (70% top)     │
  │                 │
  │  ┌───────────┐  │
  │  │ PROF GATO │  │  ← PNG del gato (fondo negro removido)
  │  └───────────┘  │
  │  SUBTÍTULOS     │  ← texto animado quemado
  └─────────────────┘
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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = BASE_DIR / "images"
MUSIC_DIR  = ASSETS_DIR / "music"

# Personaje principal — fondo negro para chroma key
GATO_PNG   = BASE_DIR / "images" / "profesor_gato_fondo_negro.jpg"
BASTET_PNG = BASE_DIR / "images" / "bastet_fondo_negro.jpg"

VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 30

# Tamaño del gato sobre el video (% del ancho)
GATO_WIDTH_PCT  = 0.75   # 75% del ancho
GATO_YPOS_PCT   = 0.52   # empieza en el 52% de la altura (mitad inferior)

# Audio
MUSIC_VOLUME     = 0.10   # música muy suave para no tapar la voz
NARRATION_VOLUME = 1.0
FADE_DURATION    = 0.8

# Subtítulos — estilo TikTok educativo
SUBTITLE_FONTSIZE  = 52
SUBTITLE_FONTCOLOR = "white"
SUBTITLE_BOXCOLOR  = "black@0.6"   # caja semitransparente detrás del texto
SUBTITLE_WORDS_PER_CHUNK = 4       # palabras por línea de subtítulo


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class VideoAssembler:

    def __init__(self, topic: str = "default"):
        self.topic = topic
        self.tmp   = Path(tempfile.mkdtemp(prefix="profgato_"))
        log.info(f"VideoAssembler iniciado | tema: {topic}")

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get_duration(self, p: Path) -> float:
        return float(ffmpeg.probe(str(p))["format"]["duration"])

    # ── PASO 1: TRANSCRIPCIÓN ─────────────────────────────────────────────────

    def transcribe_audio(self, audio_path: Path) -> list[dict]:
        """
        Transcribe el audio con Whisper y devuelve segmentos de subtítulos.
        Cada segmento = chunk de N palabras con timestamps.
        """
        log.info("Transcribiendo con Whisper...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(str(audio_path), language="es", word_timestamps=True)

        segments = []
        idx = 1
        for seg in segs:
            words = list(seg.words or [])
            if not words:
                segments.append({
                    "index": idx,
                    "start": seg.start,
                    "end":   seg.end,
                    "text":  seg.text.strip().upper()
                })
                idx += 1
                continue
            for i in range(0, len(words), SUBTITLE_WORDS_PER_CHUNK):
                chunk = words[i:i + SUBTITLE_WORDS_PER_CHUNK]
                segments.append({
                    "index": idx,
                    "start": chunk[0].start,
                    "end":   chunk[-1].end,
                    "text":  " ".join(w.word.strip() for w in chunk).upper()
                })
                idx += 1

        log.info(f"{len(segments)} segmentos de subtítulos generados")
        return segments

    def save_ass(self, segments: list[dict], duration: float) -> Path:
        """
        Genera archivo .ass (Advanced SubStation) para subtítulos quemados
        con estilo TikTok: texto blanco, caja negra semitransparente, centrado.
        """
        ass_path = self.tmp / "subtitles.ass"

        def ts(t: float) -> str:
            h  = int(t // 3600)
            m  = int((t % 3600) // 60)
            s  = int(t % 60)
            cs = int((t - int(t)) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,{SUBTITLE_FONTSIZE},&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,2,0,3,3,1,2,30,30,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for seg in segments:
            # Texto en mayúsculas, centrado
            text = seg["text"].replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{ts(seg['start'])},{ts(seg['end'])},Default,,0,0,0,,{text}")

        ass_path.write_text("\n".join(lines), encoding="utf-8")
        return ass_path

    # ── PASO 2: PREPARAR FONDO ────────────────────────────────────────────────

    def prepare_background(self, bg_image: Path, duration: float) -> Path:
        """
        Convierte la imagen de fondo (DALL-E 3) a video MP4 de la duración del audio.
        Escala y recorta para llenar exactamente 1080x1920.
        """
        out = self.tmp / "background.mp4"
        log.info(f"Preparando fondo: {bg_image.name} ({duration:.1f}s)")

        (
            ffmpeg
            .input(str(bg_image), loop=1, framerate=VIDEO_FPS, t=duration)
            .filter("scale", VIDEO_WIDTH, VIDEO_HEIGHT,
                    force_original_aspect_ratio="cover")
            .filter("crop", VIDEO_WIDTH, VIDEO_HEIGHT)
            .filter("setpts", "PTS-STARTPTS")
            .output(str(out),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    r=VIDEO_FPS,
                    t=duration,
                    preset="ultrafast",
                    crf=28)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Fondo preparado ✓")
        return out

    # ── PASO 3: PREPARAR GATO ─────────────────────────────────────────────────

    def prepare_gato(self, duration: float) -> Path:
        """
        Prepara el PNG del Profesor Gato:
        - Remueve el fondo negro (chromakey)
        - Escala al tamaño correcto
        - Genera video estático de la duración del audio
        """
        out = self.tmp / "gato.mp4"
        gato_path = GATO_PNG if GATO_PNG.exists() else None

        if not gato_path:
            log.warning("⚠️ No se encontró profesor_gato_fondo_negro.jpg")
            return None

        gato_w = int(VIDEO_WIDTH * GATO_WIDTH_PCT)
        gato_h = int(gato_w * 1.3)  # proporción aproximada del personaje

        log.info(f"Preparando gato: {gato_w}x{gato_h}px")

        (
            ffmpeg
            .input(str(gato_path), loop=1, framerate=VIDEO_FPS, t=duration)
            # Chromakey: remover fondo negro
            .filter("chromakey",
                    color="black",
                    similarity=0.25,   # tolerancia al negro
                    blend=0.05)
            # Escalar al tamaño deseado
            .filter("scale", gato_w, gato_h)
            .filter("setpts", "PTS-STARTPTS")
            .output(str(out),
                    vcodec="libx264",
                    pix_fmt="yuva420p",   # con canal alpha para transparencia
                    r=VIDEO_FPS,
                    t=duration,
                    preset="ultrafast",
                    crf=28)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Gato preparado ✓")
        return out

    # ── PASO 4: COMPONER VIDEO ────────────────────────────────────────────────

    def composite_video(self, bg: Path, gato: Path, duration: float) -> Path:
        """
        Compone el video final:
        - Fondo DALL-E ocupa todo el frame
        - Gato se posiciona en la mitad inferior, centrado horizontalmente
        """
        out = self.tmp / "composite.mp4"

        gato_w = int(VIDEO_WIDTH * GATO_WIDTH_PCT)
        gato_h = int(gato_w * 1.3)

        # Posición X: centrado
        gato_x = (VIDEO_WIDTH - gato_w) // 2
        # Posición Y: mitad inferior del frame
        gato_y = int(VIDEO_HEIGHT * GATO_YPOS_PCT)

        log.info(f"Componiendo: gato en ({gato_x}, {gato_y})")

        if gato is None:
            # Sin gato — solo fondo
            shutil.copy(bg, out)
            return out

        (
            ffmpeg
            .filter(
                [
                    ffmpeg.input(str(bg)),
                    ffmpeg.input(str(gato))
                ],
                "overlay",
                x=gato_x,
                y=gato_y,
                format="yuv420"
            )
            .output(str(out),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    r=VIDEO_FPS,
                    t=duration,
                    preset="ultrafast",
                    crf=26,
                    an=None)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Composición lista ✓")
        return out

    # ── PASO 5: QUEMAR SUBTÍTULOS ─────────────────────────────────────────────

    def burn_subtitles(self, video: Path, ass_file: Path, duration: float) -> Path:
        """
        Quema los subtítulos .ass directamente en el video.
        Resultado: texto animado con estilo TikTok educativo.
        """
        out = self.tmp / "subtitled.mp4"
        log.info("Quemando subtítulos...")

        # En Windows el path necesita las barras escapadas para el filtro subtitles
        ass_str = str(ass_file).replace("\\", "/").replace(":", "\\:")

        (
            ffmpeg
            .input(str(video))
            .filter("subtitles",
                    filename=str(ass_file),
                    force_style=f"Fontsize={SUBTITLE_FONTSIZE}")
            .output(str(out),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    r=VIDEO_FPS,
                    t=duration,
                    preset="ultrafast",
                    crf=26,
                    an=None)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Subtítulos quemados ✓")
        return out

    # ── PASO 6: MEZCLA DE AUDIO ───────────────────────────────────────────────

    def mix_audio(self, narration: Path, duration: float) -> Path:
        """
        Mezcla la narración con música de fondo lofi.
        La música se elige aleatoriamente de assets/music/
        """
        out = self.tmp / "audio_final.aac"

        music_files = []
        if MUSIC_DIR.exists():
            music_files = (
                list(MUSIC_DIR.glob("*.mp3")) +
                list(MUSIC_DIR.glob("*.wav")) +
                list(MUSIC_DIR.glob("*.m4a"))
            )

        narr = (
            ffmpeg
            .input(str(narration)).audio
            .filter("volume", NARRATION_VOLUME)
        )

        if not music_files:
            log.warning("⚠️ No hay música en assets/music/ — solo narración")
            (
                narr
                .output(str(out), acodec="aac", ar=44100)
                .overwrite_output()
                .run(quiet=True)
            )
            return out

        music = random.choice(music_files)
        log.info(f"Música: {music.name}")

        music_track = (
            ffmpeg
            .input(str(music), stream_loop=-1, t=duration).audio
            .filter("volume", MUSIC_VOLUME)
            .filter("afade", type="in",  start_time=0,               duration=FADE_DURATION)
            .filter("afade", type="out", start_time=duration - FADE_DURATION, duration=FADE_DURATION)
        )

        (
            ffmpeg
            .filter(
                [narr, music_track],
                "amix",
                inputs=2,
                duration="first",
                dropout_transition=2,
                normalize=0
            )
            .output(str(out), acodec="aac", ar=44100, t=duration)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Audio mezclado ✓")
        return out

    # ── PASO 7: MERGE FINAL ───────────────────────────────────────────────────

    def merge_final(self, video: Path, audio: Path, output_path: Path):
        """Une el video con subtítulos y el audio mezclado."""
        d = self.get_duration(video)
        log.info(f"Merge final: {output_path.name}")

        (
            ffmpeg
            .input(str(video)).video
            .filter("fade", type="in",  start_time=0,           duration=0.3)
            .filter("fade", type="out", start_time=d - FADE_DURATION, duration=FADE_DURATION)
            .output(
                ffmpeg.input(str(audio)).audio,
                str(output_path),
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                r=VIDEO_FPS,
                ar=44100,
                movflags="+faststart",
                shortest=None,
            )
            .overwrite_output()
            .run(quiet=True)
        )

    # ── PIPELINE PRINCIPAL ────────────────────────────────────────────────────

    def assemble(self,
                 audio_path: str,
                 bg_image_path: str = None,
                 output_name: str = None) -> Path:
        """
        Pipeline completo de ensamble.
        
        Args:
            audio_path:    Ruta al audio .mp3 generado por ElevenLabs
            bg_image_path: Ruta a la imagen de fondo (DALL-E 3 o fallback)
            output_name:   Nombre del archivo output sin extensión
        
        Returns:
            Path al video .mp4 final
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

        if output_name is None:
            output_name = f"profgato_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"{output_name}.mp4"

        log.info("=" * 55)
        log.info(f"🐱 ENSAMBLE: {audio_path.name}")
        log.info(f"   Output:  {output_path.name}")
        log.info("=" * 55)

        try:
            # 1. Duración del audio
            duration = self.get_duration(audio_path)
            log.info(f"Duración: {duration:.1f}s")

            # 2. Subtítulos
            segments = self.transcribe_audio(audio_path)
            ass_file = self.save_ass(segments, duration)
            # Guardar copia del .srt también
            srt_path = OUTPUT_DIR / f"{output_name}.srt"
            self._save_srt(segments, srt_path)

            # 3. Fondo
            if bg_image_path and Path(bg_image_path).exists():
                bg_img = Path(bg_image_path)
            else:
                bg_img = self._fallback_background()
            bg_video = self.prepare_background(bg_img, duration)

            # 4. Gato
            gato_video = self.prepare_gato(duration)

            # 5. Composición
            comp = self.composite_video(bg_video, gato_video, duration)

            # 6. Quemar subtítulos
            subtitled = self.burn_subtitles(comp, ass_file, duration)

            # 7. Audio
            audio_mixed = self.mix_audio(audio_path, duration)

            # 8. Merge final
            self.merge_final(subtitled, audio_mixed, output_path)

            size_mb = output_path.stat().st_size / 1024 / 1024
            log.info("=" * 55)
            log.info(f"✅ LISTO: {output_path.name} ({size_mb:.1f} MB)")
            log.info("=" * 55)

            return output_path

        except Exception as e:
            log.error(f"❌ Error en ensamble: {e}", exc_info=True)
            raise
        finally:
            self.cleanup()

    def _save_srt(self, segments: list[dict], path: Path):
        """Guarda copia en formato .srt estándar."""
        def fmt(t):
            h = int(t // 3600); m = int((t % 3600) // 60)
            s = int(t % 60);    ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        with open(path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"{seg['index']}\n")
                f.write(f"{fmt(seg['start'])} --> {fmt(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")

    def _fallback_background(self) -> Path:
        """Si no hay fondo generado, usa una imagen existente o color sólido."""
        # Buscar cualquier imagen en images/
        imgs = list(IMAGES_DIR.glob("*.png")) + list(IMAGES_DIR.glob("*.jpg"))
        # Preferir las que no son el gato
        for img in imgs:
            if "gato" not in img.name.lower() and "bastet" not in img.name.lower():
                log.info(f"Fondo fallback: {img.name}")
                return img
        # Si solo hay el gato, usarlo igual
        if imgs:
            return imgs[0]
        # Último recurso: crear imagen negra con ffmpeg
        log.warning("Sin imagen de fondo — usando negro")
        tmp_bg = self.tmp / "fallback_bg.png"
        (
            ffmpeg
            .input(f"color=c=0x1a3a2a:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}", f="lavfi", vframes=1)
            .output(str(tmp_bg))
            .overwrite_output()
            .run(quiet=True)
        )
        return tmp_bg


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN DE INTERFAZ (para main.py)
# ─────────────────────────────────────────────────────────────────────────────

def assemble_video(audio_path: str,
                   bg_image_path: str = None,
                   topic: str = "default",
                   output_name: str = None) -> str:
    return str(VideoAssembler(topic=topic).assemble(
        audio_path=audio_path,
        bg_image_path=bg_image_path,
        output_name=output_name
    ))


# ─────────────────────────────────────────────────────────────────────────────
# TEST DIRECTO
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Profesor Gato — Video Assembler")
    p.add_argument("audio",           help="Ruta al archivo de audio .mp3")
    p.add_argument("--bg",            help="Ruta a la imagen de fondo", default=None)
    p.add_argument("--topic",         help="Tema del video",            default="default")
    p.add_argument("--name",          help="Nombre del output",         default=None)
    a = p.parse_args()
    result = assemble_video(a.audio, a.bg, a.topic, a.name)
    print(f"\n✅ Video generado: {result}")
