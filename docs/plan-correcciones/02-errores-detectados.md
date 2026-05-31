# 02 — Errores Detectados

Los 4 que reportaste + lo que encontró Opus revisando el código.

---

## 🔴 E1 — Datos falsos / título no verificado

**Síntoma:** título "México organizará DOS Mundiales" (falso: 2026 es el **TERCERO**; ya organizó 1970 y 1986).

**Causa raíz (confirmada en código):**
- `script_generator.py` → `generar_script()` llama a Claude **SIN herramienta de búsqueda web**.
- `trend_detector.py` → `seleccionar_angulo_educativo()` también llama a Claude **SIN búsqueda web**.
- Claude escribe de memoria → alucina fechas, cifras y hechos.

> Verificado: `grep web_search/tools` en todo el repo → 0 resultados. No hay verificación de hechos en ningún punto.

**Por qué importa:** un canal educativo con datos erróneos pierde credibilidad.

---

## 🔴 E2 — Inconsistencia visual del personaje

**Síntoma:** el personaje "cambia de apariencia" entre paneles (gata con vestido escolar vs gato naranja con traje).

**Causas raíz (varias):**
1. **Gatos fantasma en el fondo.** `background_generator._construir_prompt()` pide "EMPTY FOREGROUND, NO cat", pero Imagen/FLUX **ignoran los negativos** y dibujan su propio gato/persona, distinto en cada panel. Ese gato del fondo + el PNG superpuesto = dos gatos distintos en pantalla.
2. **Dos personajes reales por diseño.** GATO (naranja, traje, lentes) y BASTET (calico, diadema, vestido) se alternan. Para un espectador que no sabe que son dos, parece "uno que muta". Falta etiqueta/nombre en pantalla que deje claro que es un diálogo entre dos.
3. **Outfits aleatorios = código muerto.** `_GATO_OUTFITS` / `_BASTET_OUTFITS` y `_elegir_outfit()` existen pero **no afectan nada**, porque el personaje no se genera en el fondo (es PNG fijo). Confunde.

**Lo que SÍ está bien:** usar un PNG fijo del personaje (`CHAR_PNGS`) es la decisión correcta para consistencia. El enemigo es el fondo, no el overlay.

---

## 🟠 E3 — Audio ElevenLabs cortado / con glitches

**Causas raíz probables (en `voice_synthesizer.py`):**
1. **Stability de Bastet en 0.20** (`voice_synthesizer.py:18`). Con `eleven_multilingual_v2`, una stability tan baja produce artefactos, cortes y "alucinaciones" de audio. Es la causa #1 más probable.
2. **Sin reintentos.** `requests.post` a ElevenLabs sin retry/backoff. Un 200 con cuerpo corrupto o un corte de red deja el MP3 dañado y el pipeline sigue.
3. **Sin continuidad entre paneles.** Cada panel se sintetiza aislado, sin `previous_text`/`next_text` ni `previous_request_ids`. La prosodia salta entre paneles.
4. **Concatenación frágil.** `concatenar_audios()` (en `video_assembler.py:253`) une MP3s con el demuxer `concat` re-encodeando. Sin silencio entre clips → "pop"/cortes en las uniones; si un MP3 viene dañado, contamina todo.
5. **Sin validación.** No se verifica que cada MP3 tenga duración > 0 ni tamaño razonable antes de seguir.

---

## 🟡 E4 — Código muerto y desfase de docs

1. **`clip_selector.py` entero es código muerto.** `main.py:335-339` calcula `clips_personaje` y lo pasa como `clip_personaje` en cada panel, pero `VideoAssemblerV4.crear_clip_con_overlay()` **nunca lo lee** (usa `CHAR_PNGS` fijo). Toda la lógica de "emoción por panel" no hace nada.
2. **`crear_clip_panel()`** (`video_assembler.py:154`) tampoco se usa; `ensamblar()` llama solo a `crear_clip_con_overlay()`.
3. **`_elegir_outfit()` + outfits** = muertos (ver E2.3).
4. **Docstring de `main.py` desactualizado**: dice gpt-image-2 + Claude Haiku; el código usa Imagen 4 + Sonnet 4.6. Costos estimados también desfasados.

> El código muerto no rompe el video, pero hace que cualquiera (tú o Sonnet) pierda tiempo creyendo que esas piezas hacen algo.
