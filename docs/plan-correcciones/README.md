# 🐱 Profesor Gato — Plan de Correcciones (análisis Opus)

Esta carpeta la generó **Opus** tras revisar TODO el proyecto. La idea es que tú la abras
y la ejecutes con **Sonnet** (más barato), para no gastar tokens caros de Opus en escribir código.

## Cómo usar esta carpeta

1. Abre una sesión con el modelo **Sonnet 4.6** (`/model` → Sonnet).
2. Pega el contenido de **`04-prompt-para-sonnet.md`** como primer mensaje.
3. Sonnet leerá los archivos de esta carpeta y ejecutará las tareas en orden.
4. Tú vas marcando lo que se completa.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `01-arquitectura.md` | Cómo funciona TODO el pipeline, paso a paso, con archivos y líneas. |
| `02-errores-detectados.md` | Lista completa de errores (los 4 que reportaste + los que encontró Opus). |
| `03-plan-de-correccion.md` | Tareas concretas para arreglar cada error, con snippets de código. |
| `04-prompt-para-sonnet.md` | El mensaje exacto que le pegas a Sonnet para que ejecute el plan. |

## Resumen de prioridades

| # | Problema | Gravedad | Esfuerzo |
|---|---|---|---|
| P1 | Datos falsos (título "DOS Mundiales") — no hay verificación web | 🔴 Alta | Medio |
| P2 | Inconsistencia visual del personaje (fondos con gatos extra) | 🔴 Alta | Medio |
| P3 | Audio de ElevenLabs cortado/con glitches | 🟠 Media | Bajo |
| P4 | Código muerto (clips de emoción, outfits) que confunde el mantenimiento | 🟡 Baja | Bajo |
