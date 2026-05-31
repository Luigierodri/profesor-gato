# 04 — Prompt para pegar a Sonnet

Cambia el modelo a **Sonnet 4.6** (`/model`) y pega esto como primer mensaje:

---

```
Estoy en el proyecto profesor-gato. Opus ya analizó todo y dejó un plan en
docs/plan-correcciones/. Por favor:

1. Lee docs/plan-correcciones/02-errores-detectados.md y 03-plan-de-correccion.md.
2. Ejecuta las tareas EN ORDEN (Tarea 1 → 2 → 3 → 4).
3. Para cada tarea:
   - Aplica los cambios de código indicados.
   - Si el snippet del plan no encaja exacto con el código actual, adáptalo (el plan
     es la intención, no copia literal).
   - Después de cada tarea, corre una verificación rápida y dime el resultado antes
     de pasar a la siguiente.
4. NO toques nada fuera de lo que pide el plan sin avisarme primero.

Empieza por la Tarea 1 (verificación de hechos con web search), que es la más importante.
Antes de escribir código, confírmame el plan de la Tarea 1 en 2-3 líneas.
```

---

## Pruebas que Sonnet debe correr

- **Tarea 1:** `python -c "from modules.fact_checker import generar_ficha_datos; print(generar_ficha_datos('México sede del Mundial 2026'))"` → debe decir que es el TERCER mundial.
- **Tarea 3:** `python main.py "La Guerra Fría" --audio-only` → revisar que los 6 MP3 en `audio/...` suenen completos.
- **Tarea 2 y 4:** `python main.py "La Guerra Fría"` (video completo) → revisar `videos/*.mp4`: fondos sin gatos extra, nombre del personaje visible.

## Si algo falla
- `web_search_20250305` no reconocido → `pip install -U anthropic`.
- Fuente de `drawtext` no encontrada en CI (Linux) → usar `fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`.
- Costos: revisar `tmp/cost_log.txt` tras cada run para no pasarte de presupuesto.
