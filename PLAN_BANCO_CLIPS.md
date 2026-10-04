# 🎬 Plan del Banco de Clips — Profesor Gato (GATO-CAST)

> Gemini: **3 clips de 10s por sesión**, se reinicia cada ~4h. Construimos por fases.
> Guarda los clips en `assets/hero/` y las imágenes de personaje en `assets/novela/`.
> Todo se **cablea solo** por nombre de archivo. ✅ = ya hecho.

Estilo para TODOS: mismo set/estilo pixel-art cinematográfico, 16:9, sin texto en el clip.

---

## 🥇 FASE 1 — El canal vivo (sirve en CUALQUIER video) — lo más importante

### Reacciones del Gato (cortes a su cara en momentos clave) → `assets/hero/`
- [x] `gato_react_enfasis.mp4` ✅
- [x] `gato_react_enojado.mp4` ✅
- [x] `gato_react_pensativo.mp4` ✅
- [ ] `gato_react_sorprendido.mp4` — ojos muy abiertos, boca abierta, se echa atrás
- [ ] `gato_react_rie.mp4` — risa genuina, cabeza atrás
- [ ] `gato_react_asiente.mp4` — asintiendo "claro, claro", convencido
- [ ] `gato_react_triste.mp4` — cabizbajo, conmovido (para temas duros)
- [ ] `gato_react_nervioso.mp4` — incómodo, sudando, mirando a los lados
- [ ] `gato_react_ojo.mp4` — se inclina al mic, "ojo con esto", intriga

### Entradas / hablando (para que la intro varíe) → `assets/hero/`
- [x] `gato hablando set.mp4` (entrada neutral) ✅
- [ ] `gato_hablando_2.mp4` — animado, gesticulando con las manos
- [ ] `gato_hablando_3.mp4` — serio/grave (para true crime o temas fuertes)
- [ ] `gato_hablando_intriga.mp4` — bajando la voz, "déjame contarte un secreto"

### Cierre y transiciones → `assets/hero/`
- [x] `gato_outro.mp4` ✅
- [x] `sting_gatocast.mp4` ✅
- [ ] `sting_corto.mp4` — flash de neón más rápido (0.8s) para cortes ágiles

---

## 🥈 FASE 2 — Bastet corresponsal (personalidad + alivio cómico) → `assets/hero/`

Bastet es otra gata, la **corresponsal estrella**. Habla con su propia voz. Clave:
hacer una base **reutilizable** + variantes de emoción.

- [ ] `bastet_envivo.mp4` — Bastet con micrófono de reportera, plano "en vivo",
      fondo neutro/genérico (sirve para cualquier lugar). **La más útil.**
- [ ] `bastet_asustada.mp4` — asustada/huyendo (para gags tipo "la persigue X")
- [ ] `bastet_confundida.mp4` — cara de "¿qué está pasando aquí?"
- [ ] `bastet_emocionada.mp4` — emocionada/chismosa, "¡no vas a creer esto!"
- [ ] `bastet_micro.mp4` — primer plano con micrófono, para entrevistas

> Nombre por keyword: si guardas `bastet_macondo.mp4`, el guion que diga "Macondo" lo usa.

---

## 🥉 FASE 3 — Piezas de formato (desbloquean TIPOS de video)

### True Crime (Krista Pike, casos, misterios) → `assets/hero/`
- [ ] `gato_detective.mp4` — el Gato en "modo detective" (lupa, tablero de pistas)
- [ ] `gato_hablando_grave.mp4` — tono sombrío (ya cubierto por hablando_3)
- [ ] `transicion_expediente.mp4` — se abre una carpeta de "EXPEDIENTE/CASE FILE"
- [ ] (imagen) `assets/novela/` no — para true crime las fotos reales van por el motor

### Historia / cultura
- [ ] `globo_gira.mp4` — un globo terráqueo girando (ubicar el país del tema)
- [ ] `transicion_libro.mp4` — se abre un libro antiguo (paso a lo histórico)

### Ciencia / curiosidad
- [ ] `gato_eureka.mp4` — "¡ajá!", foco encendido sobre su cabeza

---

## 🎨 FASE 4 — Personajes/escenas temáticas (por serie, reutilizable si repetimos tema)

### Cien años de soledad → `assets/novela/` (nombres simples)
- [ ] `aureliano.png` — Coronel Aureliano Buendía, estilo cine
- [ ] `pilar_ternera.png` — leyendo cartas a la luz de las velas
- [ ] `melquiades.png` — gitano escribiendo pergaminos
- [ ] `macondo.png` — el pueblo mágico
- [ ] `ursula.png`, `remedios.png` (opcionales)

> Si no las haces, el motor las **genera solas** con Nano Banana (quedó hermoso). Estas
> son para "bordar" los personajes clave con tu toque.

---

## 🧪 Ejemplo: video de **Krista Pike** (true crime) con el banco

Lo que YA tendrías del banco (reutilizable):
- Entrada: `gato_hablando_grave` + `sting_gatocast`
- Reacciones: `gato_react_sorprendido`, `gato_react_triste`, `gato_react_nervioso`
- Bastet: `bastet_envivo` (gag corto, "reportando desde el juzgado")
- Cierre: `gato_outro`
- `gato_detective` para el arranque del caso

Lo que el motor saca SOLO (fácil, por video):
- Fotos reales: mugshot, fotos del juicio, noticias → **Wikimedia / Pixabay / Openverse**
- B-roll: `prison corridor`, `courtroom`, `police lights night`, `handcuffs` → **Pixabay**
- Mapa del lugar (Tennessee) → mapa estilizado del motor
- Recreaciones (si no hay foto) → **Nano Banana** estilo cine

→ Resultado: el video de Krista Pike se arma **en una tarde**, con el banco + lo que el
motor jala solo. Entre más llenes el banco (Fases 1-2), más fácil CADA video.

---

## 📅 Orden sugerido (3 clips por sesión)

1. **Sesión 1:** `gato_react_sorprendido`, `gato_react_rie`, `gato_react_triste`
2. **Sesión 2:** `bastet_envivo`, `gato_hablando_grave`, `sting_corto`
3. **Sesión 3:** `gato_react_asiente`, `gato_react_ojo`, `gato_hablando_2`
4. **Sesión 4:** `bastet_asustada`, `bastet_confundida`, `gato_detective`
5. **Sesión 5:** `gato_hablando_3`, `globo_gira`, `gato_eureka`
6. **Sesión 6+:** personajes de novela / piezas de formato que falten

Con las **Fases 1 y 2** completas, el canal ya se siente profesional y vivo en cualquier
tema. Las demás son mejoras que sumamos sin prisa.
