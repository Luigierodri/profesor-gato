"""
fix_assembler.py
Ejecutar desde la raiz del proyecto:
  python fix_assembler.py
Reescribe modules/video_assembler.py completo y limpio.
"""
from pathlib import Path

CODE = """\
from faster_whisper import WhisperModel
import ffmpeg, logging, tempfile, shutil, random
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
VIDEOS_DIR = BASE_DIR / "videos"
MUSIC_DIR   = ASSETS_DIR / "music"
SFX_DIR     = ASSETS_DIR / "sfx"
INTRO_PATH  = ASSETS_DIR / "intro.mp4"
OUTRO_PATH  = ASSETS_DIR / "outro.mp4"

VIDEO_WIDTH      = 1080
VIDEO_HEIGHT     = 1920
VIDEO_FPS        = 30
VIDEO_FORMAT     = "mp4"
MUSIC_VOLUME     = 0.12
NARRATION_VOLUME = 1.0
FADE_DURATION    = 0.5

TOPIC_THEMES = {
    "economia":   {"bg": "chalkboard", "music": "lo_fi_study"},
    "historia":   {"bg": "ancient",    "music": "epic_ambient"},
    "cultura":    {"bg": "colorful",   "music": "upbeat_pop"},
    "default":    {"bg": "chalkboard", "music": "lo_fi_study"},
}

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("video_assembler")


class SubtitleSegment:
    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end   = end
        self.text  = text.strip().upper()

    def to_srt(self):
        def fmt(t):
            h  = int(t // 3600)
            m  = int((t % 3600) // 60)
            s  = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        return f"{self.index}\\n{fmt(self.start)} --> {fmt(self.end)}\\n{self.text}\\n"


class VideoAssembler:

    def __init__(self, topic="default"):
        self.topic = self._resolve_topic(topic)
        self.theme = TOPIC_THEMES.get(self.topic, TOPIC_THEMES["default"])
        self.tmp   = Path(tempfile.mkdtemp(prefix="profgato_"))
        log.info(f"VideoAssembler | tema: {self.topic}")

    def _resolve_topic(self, topic):
        topic = topic.lower()
        for key in TOPIC_THEMES:
            if key in topic:
                return key
        return "default"

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get_duration(self, p):
        return float(ffmpeg.probe(str(p))["format"]["duration"])

    # ── TRANSCRIPCION ─────────────────────────

    def transcribe_audio(self, audio_path):
        log.info("Transcribiendo con faster-whisper...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(str(audio_path), language="es", word_timestamps=True)
        segments = []
        idx = 1
        for seg in segs:
            words = list(seg.words or [])
            if not words:
                segments.append(SubtitleSegment(idx, seg.start, seg.end, seg.text))
                idx += 1
                continue
            for i in range(0, len(words), 5):
                chunk = words[i:i+5]
                text  = " ".join(w.word for w in chunk)
                segments.append(SubtitleSegment(idx, chunk[0].start, chunk[-1].end, text))
                idx += 1
        log.info(f"{len(segments)} segmentos generados")
        return segments

    def save_srt(self, segments):
        p = self.tmp / "subtitles.srt"
        with open(p, "w", encoding="utf-8") as f:
            for s in segments:
                f.write(s.to_srt() + "\\n")
        return p

    # ── VIDEO ─────────────────────────────────

    def prepare_background(self, duration):
        out = self.tmp / "background.mp4"
        color_map = {
            "chalkboard": "0x1a3a2a",
            "ancient":    "0x2a1a0a",
            "colorful":   "0x2a0a1a",
            "default":    "0x1a1a2a",
        }
        color = color_map.get(self.theme["bg"], "0x1a1a2a")
        log.info(f"Generando fondo: {color}")
        (
            ffmpeg
            .input(f"color=c={color}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r={VIDEO_FPS}",
                   f="lavfi", t=duration)
            .output(str(out), vcodec="libx264", pix_fmt="yuv420p")
            .overwrite_output()
            .run(quiet=True)
        )
        return out

    def assemble_clips(self, clips, duration):
        if not clips:
            return None
        out = self.tmp / "clips.mp4"
        inputs = []
        total  = 0.0
        i      = 0
        while total < duration:
            clip = Path(clips[i % len(clips)])
            cd   = min(self.get_duration(clip), duration - total)
            sc   = self.tmp / f"c{i:04d}.mp4"
            (
                ffmpeg
                .input(str(clip), t=cd)
                .filter("scale", VIDEO_WIDTH, VIDEO_HEIGHT,
                        force_original_aspect_ratio="cover")
                .filter("crop", VIDEO_WIDTH, VIDEO_HEIGHT)
                .filter("setpts", "PTS-STARTPTS")
                .output(str(sc), vcodec="libx264", pix_fmt="yuv420p",
                        r=VIDEO_FPS, an=None)
                .overwrite_output()
                .run(quiet=True)
            )
            inputs.append(str(sc))
            total += cd
            i     += 1

        lst = self.tmp / "lst.txt"
        with open(lst, "w") as f:
            for p in inputs:
                f.write(f"file '{p}'\\n")
        (
            ffmpeg
            .input(str(lst), format="concat", safe=0)
            .output(str(out), vcodec="libx264", pix_fmt="yuv420p",
                    r=VIDEO_FPS, an=None)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Clips ensamblados")
        return out

    def composite(self, bg, clips, duration):
        out = self.tmp / "comp.mp4"
        if clips is None:
            shutil.copy(bg, out)
            return out
        h = int(VIDEO_HEIGHT * 0.70)
        y = VIDEO_HEIGHT - h
        (
            ffmpeg
            .filter(
                [ffmpeg.input(str(bg)),
                 ffmpeg.input(str(clips)).filter("scale", VIDEO_WIDTH, h)],
                "overlay", x=0, y=y
            )
            .output(str(out), vcodec="libx264", pix_fmt="yuv420p",
                    r=VIDEO_FPS, t=duration, an=None)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Composicion lista")
        return out

    # ── AUDIO ─────────────────────────────────

    def mix_audio(self, narration, duration):
        out = self.tmp / "audio.aac"
        music_files = []
        if MUSIC_DIR.exists():
            music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))

        narr = ffmpeg.input(str(narration)).audio.filter("volume", NARRATION_VOLUME)

        if not music_files:
            log.info("Sin musica de fondo")
            (narr.output(str(out), acodec="aac", ar=44100)
             .overwrite_output().run(quiet=True))
            return out

        music = random.choice(music_files)
        log.info(f"Musica: {music.name}")
        music_track = (
            ffmpeg.input(str(music), stream_loop=-1, t=duration).audio
            .filter("volume", MUSIC_VOLUME)
            .filter("afade", type="in",  start_time=0, duration=FADE_DURATION)
            .filter("afade", type="out", start_time=duration-FADE_DURATION,
                    duration=FADE_DURATION)
        )
        (
            ffmpeg.filter([narr, music_track], "amix", inputs=2,
                          duration="first", dropout_transition=2, normalize=0)
            .output(str(out), acodec="aac", ar=44100, t=duration)
            .overwrite_output()
            .run(quiet=True)
        )
        log.info("Audio mezclado")
        return out

    # ── MERGE FINAL ───────────────────────────

    def merge_av(self, video, audio, output_path):
        d = self.get_duration(video)
        (
            ffmpeg.input(str(video)).video
            .filter("fade", type="out", start_time=d-FADE_DURATION,
                    duration=FADE_DURATION)
            .output(
                ffmpeg.input(str(audio)).audio,
                str(output_path),
                vcodec="libx264", acodec="aac",
                pix_fmt="yuv420p", r=VIDEO_FPS, ar=44100,
                movflags="+faststart", shortest=None,
            )
            .overwrite_output()
            .run(quiet=True)
        )
        log.info(f"Video final: {output_path}")

    # ── PIPELINE PRINCIPAL ────────────────────

    def assemble(self, audio_path, video_clips=None, output_name=None, save_srt=True):
        audio_path = Path(audio_path)
        clips      = [Path(c) for c in (video_clips or [])]

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

        if output_name is None:
            output_name = f"profgato_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        output_path = OUTPUT_DIR / f"{output_name}.{VIDEO_FORMAT}"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        log.info("=" * 50)
        log.info(f"ENSAMBLE: {audio_path.name} | clips: {len(clips)}")
        log.info("=" * 50)

        try:
            duration = self.get_duration(audio_path)
            log.info(f"Duracion: {duration:.1f}s")

            segments = self.transcribe_audio(audio_path)
            srt      = self.save_srt(segments)

            if save_srt:
                out_srt = OUTPUT_DIR / f"{output_name}.srt"
                shutil.copy(srt, out_srt)
                log.info(f"SRT guardado: {out_srt.name}")

            bg    = self.prepare_background(duration)
            cv    = self.assemble_clips(clips, duration) if clips else None
            comp  = self.composite(bg, cv, duration)
            audio = self.mix_audio(audio_path, duration)
            self.merge_av(comp, audio, output_path)

            size = output_path.stat().st_size / 1024 / 1024
            log.info("=" * 50)
            log.info(f"LISTO: {output_path.name} ({size:.1f} MB)")
            log.info("=" * 50)
            return output_path

        except Exception as e:
            log.error(f"Error: {e}", exc_info=True)
            raise
        finally:
            self.cleanup()


def assemble_video(audio_path, video_clips=None, topic="default", output_name=None):
    return str(VideoAssembler(topic=topic).assemble(
        audio_path, video_clips or [], output_name))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Profesor Gato - Video Assembler")
    p.add_argument("audio")
    p.add_argument("--clips", nargs="*", default=[])
    p.add_argument("--topic", default="default")
    p.add_argument("--name",  default=None)
    a = p.parse_args()
    print(assemble_video(a.audio, a.clips, a.topic, a.name))
"""

target = Path("modules/video_assembler.py")
target.write_text(CODE, encoding="utf-8")
print(f"OK — {target} reescrito ({len(CODE)} chars)")
