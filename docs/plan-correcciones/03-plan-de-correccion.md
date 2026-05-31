# 03 — Plan de Corrección (tareas para Sonnet)

Ejecutar **en orden**. Cada tarea es independiente y se puede commitear por separado.
Después de cada tarea: `python main.py "tema de prueba" --audio-only` (o full) para verificar.

---

## ✅ TAREA 1 — Verificación de hechos con búsqueda web (arregla E1)

**Estrategia recomendada (2 etapas, barata y controlable):**
en vez de dejar que Claude invente, primero se buscan los datos, luego se escribe el guion SOLO con esos datos.

### 1A. Nueva función "ficha de datos verificados"

Crear `modules/fact_checker.py`:

```python
"""
fact_checker.py — Genera una ficha de datos verificados con búsqueda web
antes de escribir el guion. Evita alucinaciones (fechas, cifras, hechos).
"""
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from modules import cost_tracker


def generar_ficha_datos(tema: str) -> str:
    """Devuelve una ficha breve de datos verificados sobre el tema."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        f"Investiga el tema: \"{tema}\".\n"
        "Devuelve una FICHA DE DATOS VERIFICADOS en español, en viñetas, con:\n"
        "- Fechas exactas\n- Cifras/estadísticas con su fuente y año\n"
        "- Nombres propios correctos\n- 1-2 datos sorprendentes pero CIERTOS\n"
        "Si un dato es incierto o discutido, dilo explícitamente. "
        "NO inventes nada. Máximo 12 viñetas."
    )
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=900,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": prompt}],
    )
    # Registrar costo (input/output tokens)
    cost_tracker.registrar_tokens(
        modelo=CLAUDE_MODEL,
        in_tok=msg.usage.input_tokens,
        out_tok=msg.usage.output_tokens,
        ctx=f"FactCheck: {tema[:40]}",
    )
    # Unir todos los bloques de texto de la respuesta
    return "\n".join(b.text for b in msg.content if b.type == "text").strip()
```

> Nota: la herramienta de búsqueda web de Anthropic cuesta ~$10 / 1000 búsquedas. Con `max_uses=3`
> son ~$0.03 por video. Si el SDK no reconoce `web_search_20250305`, actualizar: `pip install -U anthropic`.

### 1B. Pasar la ficha al generador de script

En `modules/script_generator.py`, modificar `generar_script` para aceptar `datos_verificados`:

```python
def generar_script(tema: str, contexto_extra: str = "", datos_verificados: str = "") -> dict:
    ...
    user_message = f"Crea un video educativo sobre: {tema}"
    if datos_verificados:
        user_message += (
            "\n\nUSA EXCLUSIVAMENTE estos DATOS VERIFICADOS. "
            "No inventes cifras, fechas ni hechos fuera de esta ficha:\n"
            f"{datos_verificados}"
        )
    if contexto_extra:
        user_message += f"\n\nContexto adicional relevante hoy: {contexto_extra}"
```

### 1C. Conectar en `main.py`

En el PASO 2 de `main.py` (antes de `generar_script`):

```python
from modules.fact_checker import generar_ficha_datos
...
banner("PASO 2 — Verificando hechos (web search)")
ficha = generar_ficha_datos(tema)
log.info(f"  Ficha de datos:\n{ficha[:300]}...")
run_log["ficha_datos"] = ficha

banner("PASO 2b — Generando script (Claude)")
script = generar_script(tema, contexto_extra=contexto_trend, datos_verificados=ficha)
```

### 1D. Reforzar el system_prompt

En `prompts/system_prompt.txt`, añadir cerca del inicio:

```
REGLA DE EXACTITUD (CRÍTICA):
- Si recibes una "FICHA DE DATOS VERIFICADOS", úsala como ÚNICA fuente de cifras, fechas y hechos.
- NUNCA inventes números, años ni "primicias". Si no estás seguro de un dato, no lo afirmes.
- El título debe ser literalmente verdadero. Ejemplo: si México será sede del Mundial 2026,
  es su TERCER mundial (1970, 1986, 2026), NO el segundo.
```

---

## ✅ TAREA 2 — Consistencia visual del personaje (arregla E2)

**Decisión de diseño:** mantener el personaje como **PNG fijo superpuesto** (ya es consistente).
El trabajo es (a) limpiar el fondo y (b) dejar claro que son DOS personajes.

### 2A. Fondos sin figuras (reforzar prompt + framing)

En `background_generator._construir_prompt()`, para los paneles que NO son classroom,
forzar plano amplio sin seres vivos:

```python
return (
    f"{_PIXEL_STYLE}. "
    f"Real-world location: {location}. "
    "WIDE ESTABLISHING SHOT, scenery and architecture only, empty of any living being. "
    "Absolutely NO people, NO cats, NO animals, NO characters, NO silhouettes, NO crowds. "
    f"Visual context (as background scenery only): {visual_pizarron}. "
    "NO text, NO numbers, NO letters anywhere."
)
```

Y para classroom, igual: "empty classroom, no people, no cats". (El positivo "wide establishing shot"
ayuda más que el negativo, porque Imagen tiende a no poner figuras en planos amplios.)

### 2B. Nameplate por personaje (deja claro que son dos)

En `video_assembler.crear_clip_con_overlay()`, tras superponer el PNG, dibujar el nombre del que habla.
Añadir un `drawtext` (requiere fuente; en Windows usar una ruta de fuente del sistema o `Arial`):

```python
nombre = "PROFESOR GATO" if speaker == "gato" else "BASTET"
video = video.filter(
    "drawtext",
    text=nombre,
    fontcolor="white", fontsize=44, borderw=3, bordercolor="black",
    x="(w-text_w)/2", y="h-h*0.06",   # bajo el personaje
    fontfile="C\\:/Windows/Fonts/arialbd.ttf",  # escapado para el parser de ffmpeg en Windows
)
```

> Alternativa más robusta: añadir el nombre como un estilo extra en el `.ass` de subtítulos.
> Probar primero `drawtext`; si da problemas de fuente en el CI (Linux), usar `DejaVuSans-Bold.ttf`.

### 2C. (Opcional) Guard de "fondo con figura"

Si quieres ser estricto: tras generar el fondo, pedir a un modelo barato de visión que responda
"¿hay algún personaje/animal en primer plano? sí/no" y regenerar si "sí". Es costo extra; dejarlo
como mejora futura, no bloqueante.

---

## ✅ TAREA 3 — Arreglar el audio de ElevenLabs (arregla E3)

### 3A. Subir stability de Bastet

En `voice_synthesizer.py:17`, cambiar `stability` de `0.20` a `0.40` (menos artefactos,
sigue siendo expresiva):

```python
BASTET_VOICE_SETTINGS = {
    "stability":        0.40,   # antes 0.20 (causaba glitches)
    "similarity_boost": 0.70,
    "style":            0.55,
    "use_speaker_boost": True,
}
```

### 3B. Reintentos + validación

Envolver la llamada a ElevenLabs en `generar_audios_por_paneles` con retry y validación de duración:

```python
import time

def _post_elevenlabs(url, headers, payload, intentos=3):
    for i in range(intentos):
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code == 200 and len(r.content) > 2000:  # mp3 mínimamente válido
            return r
        time.sleep(2 ** i)  # backoff: 1s, 2s, 4s
    raise Exception(f"ElevenLabs falló tras {intentos} intentos [{r.status_code}]: {r.text[:200]}")
```

Y tras guardar el MP3, validar duración:

```python
duracion = obtener_duracion_audio(ruta_audio)
if duracion < 0.3:
    raise Exception(f"Audio panel {numero} sospechosamente corto ({duracion:.2f}s)")
```

### 3C. Continuidad entre paneles (prosodia)

Pasar el texto del panel anterior/siguiente para que ElevenLabs no "salte":

```python
payload = {
    "text": narracion,
    "model_id": ELEVENLABS_MODEL,
    "voice_settings": voice_settings,
    "previous_text": paneles[idx-1]["narracion"] if idx > 0 else None,
    "next_text":     paneles[idx+1]["narracion"] if idx < len(paneles)-1 else None,
}
```

(Requiere iterar con `enumerate(paneles)` para tener `idx`.)

### 3D. Silencio entre clips al concatenar

En `concatenar_audios()` (`video_assembler.py:253`), insertar 150 ms de silencio entre paneles
para evitar "pops" en las uniones. Lo más simple: generar un `silence.mp3` con
`anullsrc` y alternarlo en la lista de concat, o re-encodear con `apad`/`adelay`.
Mínimo viable: añadir `-af "apad=pad_dur=0.1"` por clip antes de concatenar.

---

## ✅ TAREA 4 — Limpiar código muerto (arregla E4)

1. **Borrar** `modules/clip_selector.py` y sus usos en `main.py` (líneas 53, 334-339, y `"clip_personaje": str(clip)` en 376, y la variable `clip` del `zip` en 378).
   - O, si quieres personajes animados en vez de PNG fijo, **cablearlo de verdad** pasando
     `clip_personaje` a `crear_clip_con_overlay` y usándolo como overlay. Decisión tuya;
     lo simple/consistente es borrarlo.
2. **Borrar** `_GATO_OUTFITS`, `_BASTET_OUTFITS`, `_elegir_outfit`, `outfit_seed` de `background_generator.py` (no afectan nada).
3. **Borrar** `crear_clip_panel()` de `video_assembler.py` (no se usa).
4. **Actualizar** el docstring de `main.py` (líneas 8-26): Imagen 4 (no gpt-image-2), Sonnet 4.6 (no Haiku), y recalcular el costo estimado por video.

---

## Orden de commits sugerido

```
fix: verificación de hechos con web search antes del script   (Tarea 1)
fix: fondos sin figuras + nameplate de personaje              (Tarea 2)
fix: audio ElevenLabs — stability, retry, continuidad         (Tarea 3)
chore: eliminar código muerto (clip_selector, outfits)        (Tarea 4)
docs: actualizar docstring de main.py
```
