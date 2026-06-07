"""Convierte PNG con fondo NEGRO -> fondo TRANSPARENTE (flood-fill desde los bordes).

Uso:
  python tools/quitar_fondo.py images/personajes/gato            # toda la carpeta
  python tools/quitar_fondo.py images/personajes/gato/gato_gancho.png   # un archivo

Conserva los negros INTERIORES (ojos, contornos, lentes): solo borra el negro
conectado al borde de la imagen. Sobrescribe el archivo con su versión transparente.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

THRESH = 40                 # tolerancia: qué tan "negro" cuenta como fondo
SENTINEL = (1, 254, 1)      # color temporal para marcar el fondo


def quitar(path: Path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()

    # Semillas: pixeles del borde que son casi negros
    seeds = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
    seeds += [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]

    for (x, y) in seeds:
        r, g, b = px[x, y]
        if r <= THRESH and g <= THRESH and b <= THRESH:
            ImageDraw.floodfill(img, (x, y), SENTINEL, thresh=THRESH)

    # Donde quedó el color centinela -> transparente; el resto -> opaco
    rgba = img.convert("RGBA")
    rgba.putdata([
        (0, 0, 0, 0) if (r, g, b) == SENTINEL else (r, g, b, 255)
        for (r, g, b, _a) in rgba.getdata()
    ])
    rgba.save(path)
    print(f"  OK  {path.name}  -> transparente")


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/quitar_fondo.py <archivo.png | carpeta>")
        return
    target = Path(sys.argv[1])
    files = [target] if target.is_file() else sorted(target.glob("*.png"))
    if not files:
        print("No se encontraron PNG en esa ruta.")
        return
    for f in files:
        quitar(f)
    print(f"Listo: {len(files)} imagen(es) convertida(s).")


if __name__ == "__main__":
    main()
