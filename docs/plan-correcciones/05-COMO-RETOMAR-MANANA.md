# 🌅 Cómo retomar mañana (guía rápida)

> Escrito por Opus la noche del 30 may 2026 mientras dormías. Todo lo del plan **ya está implementado y commiteado**. Esto es lo que queda y cómo seguir.

---

## ⚠️ LO PRIMERO (importante)

**Desactivé el run automático de GitHub Actions** para que NO se publicara otro video con problemas a las 7am (antes de que despertaras) y te dieran otro strike.

- Estado actual: workflow **"Profesor Gato - Run Diario"** = `disabled_manually`.
- **NO se reactiva solo.** Reactívalo TÚ cuando hayas revisado un video completo y estés conforme:
  ```
  gh workflow enable 285892585
  ```

**El video bloqueado en YouTube** ("México organizará DOS Mundiales"): bórralo o sube la versión corregida. No intentes "resolver la reclamación" — el problema era música con copyright + duración ≥60s, ya arreglado para los próximos.

---

## ✅ Lo que YA quedó hecho (rama `fix/calidad-y-copyright`)

| # | Arreglo | Estado |
|---|---|---|
| P0-A | Short < 60s (reduje palabras + acelero audio si se pasa) | ✅ probado (50.1s) |
| P0-B | Música sin copyright (solo Lyria; sin tracks de SoundCloud) | ✅ implementado |
| E1 | Verificación de hechos con web search antes del guion | ✅ **probado** |
| E2 | Fondos sin gatos fantasma + nameplate (PROFESOR GATO / BASTET) | ✅ implementado |
| E3 | Audio ElevenLabs: stability 0.40, retry, continuidad, pad | ✅ probado |
| E4 | Borré código muerto (clip_selector, outfits, crear_clip_panel) | ✅ implementado |

**Prueba end-to-end de audio que corrí** (tema "Mundial 2026"):
- Título generado: **"El Azteca hará historia en el Mundial 2026"** ✅ (antes alucinaba "DOS Mundiales")
- Lección: *"primer estadio en albergar tres Copas del Mundo: 1970, 1986 y 2026"* ✅ correcto
- Duración: 50.1s ✅ Short válido

---

## 📋 Lo que FALTA por hacer tú (en orden)

### 1. Probar un VIDEO completo (no solo audio)
Yo solo pude probar el audio (el video gasta créditos de Vertex/fal). Corre:
```
cd C:\Users\luigi\Desktop\profesor-gato
.venv\Scripts\python.exe main.py "México será sede del Mundial 2026"
```
Luego abre el MP4 en `videos/` y **verifica con tus ojos**:
- [ ] Dura menos de 60s.
- [ ] Sale el nombre en pantalla (PROFESOR GATO en dorado / BASTET en cian) → debe quedar claro que son dos.
- [ ] Los fondos NO tienen gatos/personas extra peleando con el personaje superpuesto.
- [ ] La música es de Lyria (o no hay música), nunca un track de `assets/music/`.
- [ ] El audio suena continuo, sin cortes ni glitches.

### 2. Si algo del video no convence
- **Nameplate tapa los subtítulos o queda mal** → ajusta `MarginV` de los estilos `NameGato`/`NameBastet` en `modules/video_assembler.py` (función `generar_ass`).
- **Sigue saliendo un gato en el fondo** → el modelo Imagen ignora negativos; sube el peso del plano amplio o considera el "guard de visión" (Tarea 2C del plan original).
- **Lyria falla siempre y los videos quedan sin música** → consigue música realmente libre (YouTube Audio Library) y reemplaza `assets/music/`, o pon `ALLOW_STATIC_MUSIC=true` SOLO si verificaste que esos tracks no tienen Content ID.

### 3. Mergear a master y reactivar
Cuando un video te convenza:
```
git checkout master
git merge fix/calidad-y-copyright
git push
gh workflow enable 285892585
```

---

## 🔁 Si quieres seguir mejorando con Sonnet (barato)
Cambia a Sonnet y pídele tareas concretas, p. ej.:
- "Añade el hashtag #Shorts y verifica que publisher.py suba como Short."
- "Implementa el guard de visión de la Tarea 2C para detectar gatos en el fondo."

El plan completo y el detalle técnico están en los otros archivos de esta carpeta y en Notion
("Análisis Opus + Plan de Correcciones").

---

## 📦 Resumen de commits (rama `fix/calidad-y-copyright`)
```
chore: E4 — eliminar código muerto + docstring actualizado
fix:   E3 — audio ElevenLabs robusto
feat:  E2 — consistencia visual (fondos sin figuras + nameplate)
feat:  E1 — verificación de hechos con web search antes del guion
fix:   P0 — Short <60s (atempo guard) + música sin copyright (solo Lyria)
docs:  plan de correcciones (esta carpeta)
```
Todo está commiteado en local. **No hice push** — master sigue intacto hasta que tú decidas.
