# Personajes — poses rotables

Cada personaje tiene varias poses (una por emoción/rol narrativo). El pipeline
elige la pose según el panel del guion (ver `video_assembler.py`).

## Specs de cada PNG
- Fondo NEGRO PURO (#000000), sin sombras ni degradados (el motor lo elimina por colorkey).
- Un solo personaje, cuerpo completo, centrado, de pie, pies cerca del borde inferior.
- Mismo diseño/vestuario/colores en todas las poses del personaje.
- Retrato vertical ~2:3. Sin objetos negros nuevos (se volverían transparentes).

## Nombres de archivo (exactos)

### gato/
- gato_gancho.png    → Panel 1 (gancho, intenso/señalando)
- gato_explica.png   → Panel 3 (explicando con el puntero)
- gato_revela.png    → Panel 5 (el giro/bomba, ojos abiertos)
- gato_cierre.png    → Panel 6 (cierre cálido, invitando)
- gato_senala.png    → señala el gráfico/foto (úsala en segmentos con `visual` foto/grafica)
- gato_indignado.png → rabia justa ante el abuso/dato injusto
- gato_piensa.png    → reflexivo, plantea la duda
- gato_dinero.png    → magnate estilo Monopoly (beats de codicia/renta/quién se queda el dinero)

### bastet/
- bastet_sorpresa.png    → Panel 2 (asombro)
- bastet_pregunta.png    → reacción curiosa (cabeza ladeada)
- bastet_preocupada.png  → Panel 4 (inquietud)
- bastet_eureka.png      → revelación feliz ("¡ya entendí!")
- bastet_senala.png      → señala el gráfico/foto
- bastet_indignada.png   → molesta ante la injusticia
- bastet_asombrada.png   → asombro grande (boca abierta, patas arriba)
- bastet_triste.png      → desánimo ante la mala noticia

### nilo/
- (por definir)

## Fallback
Si una pose no existe, el motor usa el PNG raíz del personaje
(images/profesor_gato_fondo_negro.png / images/bastet_fondo_negro.png).
