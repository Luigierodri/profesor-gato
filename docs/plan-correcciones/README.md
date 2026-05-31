# 🐱 Profesor Gato — Plan de Correcciones (análisis Opus)

> **ACTUALIZACIÓN (30 may, 23:50):** Opus ya NO solo planeó — **implementó y commiteó las 6 correcciones**
> en la rama `fix/calidad-y-copyright`. 👉 **Empieza por [`05-COMO-RETOMAR-MANANA.md`](05-COMO-RETOMAR-MANANA.md).**

Esta carpeta la generó **Opus** tras revisar TODO el proyecto. El plan original era ejecutarlo con
Sonnet, pero pediste usar todos los créditos de la sesión, así que Opus lo implementó directo.

## Cómo retomar

1. Lee **`05-COMO-RETOMAR-MANANA.md`** (qué quedó hecho, qué falta, y que el run diario está PAUSADO).
2. Prueba un video completo y revísalo.
3. Si convence: merge a master + reactivar el workflow.

Los archivos 01-04 son el análisis y el plan técnico original (referencia).

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
