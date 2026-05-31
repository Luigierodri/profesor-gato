# 01 — Arquitectura del Pipeline (cómo funciona TODO)

Punto de entrada: **`main.py`** → función `correr_pipeline()`. Genera **1 video por ejecución**.

```
python main.py                  # tema automático (trends)
python main.py "La Guerra Fría" # tema manual
python main.py --audio-only     # solo audio (sin video)
```

## Flujo completo (7 pasos)

| Paso | Módulo / función | Qué hace | API / costo |
|---|---|---|---|
| **1. Tema** | `modules/trend_detector.py` → `detectar_temas_del_dia()` + `seleccionar_angulo_educativo()` | Lee Google Trends RSS (MX/AR/CO/CL/PE), NewsAPI, Reddit. Claude convierte un trend viral en un "ángulo educativo". Si no hay trends → lista `_TEMAS_RESPALDO` rotativa (60 temas) en `main.py:175`. | Claude (Sonnet 4.6) |
| **2. Script** | `modules/script_generator.py` → `generar_script()` | Claude escribe el guion en JSON: `titulo`, `leccion`, `paneles[]` (6), `musica_mood`, `ambiente_sonoro`, `hashtags`. Usa `prompts/system_prompt.txt`. | Claude (Sonnet 4.6) |
| **3. Paneles** | `main.py` → `script_a_paneles()` | Normaliza los 6 paneles, calcula `duracion_aprox` por nº de palabras. | — |
| **4. Voz** | `modules/voice_synthesizer.py` → `generar_audios_por_paneles()` | 1 MP3 por panel. GATO usa `VOICE_ID` (voz clonada de Luigie); BASTET usa `BASTET_VOICE_ID` (Matilda). Modelo `eleven_multilingual_v2`. | ElevenLabs |
| **5. Imágenes (fondo)** | `modules/background_generator.py` → `generar_imagenes_por_paneles()` | 1 imagen de **FONDO** por panel, pixel art 16-bit. Cadena de fallback: Imagen 4 → Imagen 3 → FLUX Schnell → gpt-image-1. El fondo NO debe tener personaje (se superpone después). | Vertex AI / fal.ai / OpenAI |
| **5.5 Animar** | `modules/video_animator.py` → `animar_paneles()` | Anima cada imagen con fal.ai Kling 1.6 (parallax). | fal.ai |
| **5.7 Clips personaje** | `modules/clip_selector.py` → `elegir_clip_personaje()` | Elige un clip de emoción por panel. ⚠️ **CÓDIGO MUERTO: el resultado nunca se usa** (ver errores E4). | — |
| **5.8 Ambiente** | `modules/sound_generator.py` → `generar_ambiente()` | SFX ambiental contextual (ej. multitud, batalla). | — |
| **5.9 Música** | `modules/music_generator.py` → `generar_musica_lyria()` | Música contextual con Lyria 3; si falla, usa tracks estáticos de `assets/music/<mood>/`. | Vertex AI |
| **6. Ensamble** | `modules/video_assembler.py` → `VideoAssemblerV4.ensamblar()` | Une todo. Ver detalle abajo. | ffmpeg local |
| **7. Publicar** | `publisher.py`, `tiktok_publisher.py` | Sube a YouTube/TikTok. (En `main.py` solo está como log "PROXIMAMENTE".) | — |

## Detalle del ensamble (`VideoAssemblerV4`)

Orden real dentro de `ensamblar()`:

1. **`crear_clip_con_overlay()`** (por panel):
   - **Fondo** = clip animado de Kling (`ruta_video`) escalado a 1080×1920, o Ken Burns sobre la imagen estática si no hay animación.
   - **Personaje** = se superpone un **PNG fijo**: `images/profesor_gato_fondo_negro.png` (gato) o `images/bastet_fondo_negro.png` (bastet). Definido en `CHAR_PNGS` (`video_assembler.py:42`). Se posiciona centrado abajo, al 45% del ancho.
   - **Audio** = narración del panel.
2. **`concatenar_clips()`** → video continuo.
3. **`concatenar_audios()`** → un solo MP3 (concat demuxer, re-encode a mp3 44100).
4. **`transcribir()`** con faster-whisper (modelo `base`, CPU) → subtítulos.
5. **`generar_ass()` + `quemar_subtitulos()`** → subtítulos estilo TikTok quemados.
6. **`mezclar_audio()`** → 3 capas: narración (100%) + ambiente (15%) + música Lyria/estática (10%).
7. **`merge_final()`** → fuerza 1080×1920, fade in/out, MP4 final en `videos/`.

## Dato CLAVE para entender el problema visual

> El personaje **NO** se genera con IA por panel. Es un **PNG fijo superpuesto**.
> El fondo SÍ se genera con IA y se le pide "EMPTY FOREGROUND, no cat".
> El problema: los modelos de imagen **ignoran los negativos** y meten un gato/persona en el fondo,
> que se ve distinto en cada panel → choca con el PNG fijo → sensación de "el personaje cambia".

## Configuración (`config.py`)

- `CLAUDE_MODEL = "claude-sonnet-4-6"` (script y ángulo).
- `ELEVENLABS_MODEL = "eleven_multilingual_v2"`.
- `VOICE_SETTINGS` (gato): stability 0.45, similarity 0.85, style 0.35.
- `BASTET_VOICE_SETTINGS` (en `voice_synthesizer.py:17`): stability **0.20** (muy baja → glitches), similarity 0.60, style 0.80.
- Resolución 1080×1920, 30 fps.

## Desfase de documentación detectado

El docstring de `main.py` (líneas 8-26) dice "gpt-image-2" y "Claude Haiku", pero el código real
usa **Imagen 4 (Vertex)** y **Sonnet 4.6**. Está desactualizado.
