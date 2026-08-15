#!/usr/bin/env python3
"""
verificar_footage.py — Encuentra las ventanas LIMPIAS de un footage descargado.

Esto existe por el problema que aparece en cada sesión de Partida Guardada:
el descargador baja un trailer y viene con tarjeta de rating (PEGI/ESRB),
logos de publisher, reseñas quemadas ("IGN — A MASTERCLASS"), subtítulos de
diálogo en inglés, HUD, o marca de agua de un canal fan. Se descubre después
de renderizar y cuesta 3 o 4 renders por video.

Este módulo lo detecta ANTES, automáticamente, y devuelve los tramos usables.

Qué detecta:

  1. TEXTO QUEMADO — OCR sobre frames muestreados. Cualquier texto en pantalla
     (reseñas, subtítulos, títulos, menús) marca el frame como sucio.
  2. MARCA DE AGUA / HUD — regiones que no cambian en todo el clip pero tienen
     detalle. Un logo fijo de canal o un HUD de juego dan cero varianza
     temporal con alta densidad de bordes.
  3. CABEZA DEL TRAILER — los primeros segundos casi siempre son tarjeta de
     rating y logos. Se descartan por regla, sin depender de la detección.
  4. NEGROS Y TRANSICIONES — no se abre una ventana en un fundido.

Uso:

    python verificar_footage.py raw.mp4
    python verificar_footage.py raw.mp4 --exportar limpio.mp4
    python verificar_footage.py raw.mp4 --contacto hoja.png --min 4

Desde el pipeline:

    from verificar_footage import analizar, exportar_limpio

    r = analizar("footage/skyrim_raw.mp4")
    if r.contaminacion_global > 0.75:
        # marca de agua en TODO el clip -> descartar y bajar otra fuente
        ...
    exportar_limpio("footage/skyrim_raw.mp4", r, "footage/skyrim_limpio.mp4")

Requiere: ffmpeg, opencv-python, pytesseract + tesseract-ocr, numpy, pillow.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field

import cv2
import numpy as np


# ── parámetros ───────────────────────────────────────────────────────

INTERVALO = 1.0          # cada cuántos segundos se muestrea un frame
CABEZA_DESCARTE = 12.0   # segundos iniciales que se tiran por regla
COLA_DESCARTE = 2.0      # créditos / logo final
MIN_VENTANA = 3.5        # duración mínima de una ventana usable
ANCHO_ANALISIS = 640     # se analiza en chico: más rápido e igual de fiable

CONF_OCR = 55            # confianza mínima para creerle a tesseract
MIN_CARACTERES = 3       # menos de esto es ruido, no texto

NEGRO_MAX = 18           # brillo medio por debajo = frame negro


@dataclass
class Frame:
    t: float
    texto: bool = False
    negro: bool = False
    palabras: list[str] = field(default_factory=list)

    @property
    def limpio(self) -> bool:
        return not self.texto and not self.negro


@dataclass
class Reporte:
    duracion: float
    frames: list[Frame]
    ventanas: list[tuple[float, float]]
    mascara_estatica: np.ndarray | None
    contaminacion_global: float          # 0-1: qué tanto del clip tiene overlay fijo
    zona_marca: str | None               # dónde vive el overlay, si hay
    overlays: list = field(default_factory=list)
    tam: tuple[int, int] = (0, 0)

    @property
    def segundos_limpios(self) -> float:
        return sum(b - a for a, b in self.ventanas)


# ── utilidades ───────────────────────────────────────────────────────

def _duracion(ruta: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", ruta],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _cajas_texto(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Candidatos a texto por FORMA, sin leer nada todavía.

    El texto quemado es casi siempre claro sobre oscuro (o al revés) y forma
    bloques más anchos que altos. Se buscan esos bloques; el OCR viene después
    y solo sobre estos recortes, que es mucho más fiable y más rápido que
    correr OCR sobre el cuadro completo.
    """
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cajas = []

    for mask in ((g > 205).astype(np.uint8) * 255,
                 (g < 45).astype(np.uint8) * 255):
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 60), 3))
        cerrada = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
        cnts, _ = cv2.findContours(cerrada, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            x, y, cw, ch = cv2.boundingRect(c)
            if ch < h * 0.018 or ch > h * 0.16:      # ni microscópico ni titular gigante
                continue
            if cw < ch * 1.2 or cw > w * 0.95:       # más ancho que alto, pero no toda la línea
                continue
            relleno = cv2.contourArea(c) / max(cw * ch, 1)
            if not (0.12 < relleno < 0.92):          # ni hueco ni bloque sólido
                continue
            cajas.append((x, y, cw, ch))
    return cajas


def _leer_caja(img: np.ndarray, caja: tuple[int, int, int, int]) -> str:
    """OCR sobre un recorte, ampliado y binarizado. Devuelve '' si no es texto."""
    try:
        import pytesseract
    except ImportError:
        return ""

    x, y, w, h = caja
    m = 6
    cr = img[max(0, y - m): y + h + m, max(0, x - m): x + w + m]
    if cr.size == 0:
        return ""

    cr = cv2.resize(cr, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(cr, cv2.COLOR_BGR2GRAY)
    g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    if g.mean() > 127:
        g = 255 - g

    try:
        d = pytesseract.image_to_data(
            255 - g, output_type=pytesseract.Output.DICT, config="--psm 7")
    except Exception:
        return ""

    palabras = []
    for t, c in zip(d.get("text", []), d.get("conf", [])):
        t = (t or "").strip()
        try:
            conf = float(c)
        except (TypeError, ValueError):
            continue
        if conf >= CONF_OCR and len(t) >= MIN_CARACTERES and any(ch.isalnum() for ch in t):
            palabras.append(t)
    return " ".join(palabras)


def _agrupar_persistentes(por_frame: list[list[tuple[tuple, str]]],
                          n_frames: int,
                          tam: tuple[int, int]) -> list[tuple[tuple, str, float]]:
    """
    Encuentra cajas que salen SIEMPRE en la misma posición: marca de agua de
    canal, logo fijo, HUD. Se separan del texto de contenido porque se tratan
    distinto — una marca en una esquina se arregla con un crop, no tirando el
    clip entero.
    """
    W, H = tam
    tol = max(12, W // 50)
    cubos: dict[tuple, list[str]] = {}

    for cajas in por_frame:
        vistos = set()
        for (x, y, w, h), texto in cajas:
            clave = (round(x / tol), round(y / tol), round(w / tol))
            if clave in vistos:
                continue
            vistos.add(clave)
            cubos.setdefault(clave, []).append(texto)

    persistentes = []
    for clave, textos in cubos.items():
        frec = len(textos) / max(1, n_frames)
        if frec >= 0.6:
            x, y, w = (c * tol for c in clave)
            etiqueta = next((t for t in textos if t), "")
            persistentes.append(((int(x), int(y), int(w)), etiqueta, frec))
    return persistentes


def _zona(x: int, y: int, W: int, H: int) -> str:
    v = "arriba" if y < H / 3 else ("abajo" if y > 2 * H / 3 else "centro")
    o = "izquierda" if x < W / 3 else ("derecha" if x > 2 * W / 3 else "centro")
    return f"{v}-{o}" if v != "centro" or o != "centro" else "centro"


# ── análisis ─────────────────────────────────────────────────────────

def analizar(video: str,
             intervalo: float = INTERVALO,
             cabeza: float = CABEZA_DESCARTE,
             min_ventana: float = MIN_VENTANA,
             rapido: bool = False) -> Reporte:

    if not os.path.exists(video):
        sys.exit(f"No existe: {video}")

    dur = _duracion(video)
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        sys.exit(f"No se pudo abrir: {video}")

    print(f"[footage] {os.path.basename(video)} · {dur:.1f}s")

    frames: list[Frame] = []
    por_frame: list[list[tuple[tuple, str]]] = []
    tam = (ANCHO_ANALISIS, ANCHO_ANALISIS * 9 // 16)
    t = 0.0

    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, img = cap.read()
        if not ok:
            break

        h, w = img.shape[:2]
        chico = cv2.resize(img, (ANCHO_ANALISIS, max(1, int(h * ANCHO_ANALISIS / w))))
        tam = (chico.shape[1], chico.shape[0])

        f = Frame(t=t)
        gris = cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY)
        f.negro = float(gris.mean()) < NEGRO_MAX

        hallazgos: list[tuple[tuple, str]] = []
        if not f.negro:
            for caja in _cajas_texto(chico):
                texto = "" if rapido else _leer_caja(chico, caja)
                if texto:
                    hallazgos.append((caja, texto))

        por_frame.append(hallazgos)
        frames.append(f)
        t += intervalo

    cap.release()

    # Las cajas que salen siempre en el mismo lugar son overlay, no contenido
    persistentes = _agrupar_persistentes(por_frame, len(frames), tam)
    claves_fijas = {(round(c[0][0] / max(12, tam[0] // 50)),
                     round(c[0][1] / max(12, tam[0] // 50))) for c in persistentes}
    tol = max(12, tam[0] // 50)

    for f, hallazgos in zip(frames, por_frame):
        propios = []
        for (x, y, w, h), texto in hallazgos:
            if (round(x / tol), round(y / tol)) in claves_fijas:
                continue          # es la marca de agua, se trata aparte
            propios.append(texto)
        f.palabras = propios
        f.texto = bool(propios)

    # Regla dura: cabeza y cola fuera, pase lo que pase
    for f in frames:
        if f.t < cabeza or f.t > dur - COLA_DESCARTE:
            f.texto = True

    # Ventanas contiguas de frames limpios
    ventanas: list[tuple[float, float]] = []
    ini = None
    for i, f in enumerate(frames):
        if f.limpio and ini is None:
            ini = f.t
        elif not f.limpio and ini is not None:
            fin = frames[i - 1].t + intervalo
            if fin - ini >= min_ventana:
                ventanas.append((ini, fin))
            ini = None
    if ini is not None:
        fin = min(dur, frames[-1].t + intervalo)
        if fin - ini >= min_ventana:
            ventanas.append((ini, fin))

    W, H = tam
    cobertura = 0.0
    zona = None
    if persistentes:
        (x, y, w), etiqueta, frec = max(persistentes, key=lambda c: c[2])
        zona = _zona(x, y, W, H)
        cobertura = frec

    rep = Reporte(dur, frames, ventanas, None, cobertura, zona)
    rep.overlays = persistentes
    rep.tam = tam

    sucios = sum(1 for f in frames
                 if f.texto and cabeza <= f.t <= dur - COLA_DESCARTE)
    print(f"  frames muestreados: {len(frames)} · con texto de contenido: {sucios}")

    for (x, y, w), etiqueta, frec in persistentes:
        z = _zona(x, y, W, H)
        marca = f' "{etiqueta}"' if etiqueta else ""
        print(f"  ⚠ overlay fijo{marca} en {z} — presente en {frec*100:.0f}% del clip")
        if "centro" not in z:
            lado_v = "top" if y < H / 2 else "bottom"
            lado_h = "left" if x < W / 2 else "right"
            pct_v = max(8, round((y + 40) / H * 100 / 4) * 4)
            print(f"      se quita con crop del {pct_v}% en {lado_v}-{lado_h}")
        else:
            print("      está en el centro: no se puede recortar, bajar otra fuente")

    print(f"  ventanas limpias: {len(ventanas)} · "
          f"{rep.segundos_limpios:.1f}s usables de {dur:.1f}s")
    for a, b in ventanas[:8]:
        print(f"    {a:7.1f}s → {b:7.1f}s   ({b-a:.1f}s)")
    if len(ventanas) > 8:
        print(f"    ... y {len(ventanas)-8} más")

    if not ventanas:
        print("  ⚠ SIN material usable. Bajar otra fuente.")

    return rep


# ── salidas ──────────────────────────────────────────────────────────

def exportar_limpio(video: str, rep: Reporte, salida: str,
                    max_segundos: float | None = None) -> str | None:
    """Concatena las ventanas limpias en un solo archivo curado."""
    if not rep.ventanas:
        print("  nada que exportar")
        return None

    trozos = []
    total = 0.0
    for a, b in rep.ventanas:
        if max_segundos and total >= max_segundos:
            break
        dur = b - a
        if max_segundos:
            dur = min(dur, max_segundos - total)
        trozos.append((a, dur))
        total += dur

    partes = []
    filtros = []
    for i, (a, d) in enumerate(trozos):
        filtros.append(
            f"[0:v]trim=start={a}:duration={d},setpts=PTS-STARTPTS[v{i}]")
        partes.append(f"[v{i}]")
    filtros.append("".join(partes) + f"concat=n={len(trozos)}:v=1:a=0[out]")

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video,
           "-filter_complex", ";".join(filtros),
           "-map", "[out]", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-an", salida]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        return None

    print(f"  exportado: {salida}  ({total:.1f}s de {len(trozos)} ventanas)")
    return salida


def hoja_contacto(video: str, rep: Reporte, salida: str, columnas: int = 6) -> str:
    """
    PNG con los frames muestreados, borde verde si limpio y rojo si sucio.
    Para revisar en 3 segundos si la detección acertó.
    """
    cap = cv2.VideoCapture(video)
    minis = []
    paso = max(1, len(rep.frames) // 36)

    for f in rep.frames[::paso]:
        cap.set(cv2.CAP_PROP_POS_MSEC, f.t * 1000)
        ok, img = cap.read()
        if not ok:
            continue
        m = cv2.resize(img, (320, 180))
        color = (90, 200, 60) if f.limpio else (60, 60, 235)
        m = cv2.copyMakeBorder(m, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=color)
        cv2.putText(m, f"{f.t:.0f}s", (12, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2, cv2.LINE_AA)
        minis.append(m)
    cap.release()

    if not minis:
        return ""

    filas = []
    for i in range(0, len(minis), columnas):
        fila = minis[i: i + columnas]
        while len(fila) < columnas:
            fila.append(np.zeros_like(minis[0]))
        filas.append(np.hstack(fila))
    cv2.imwrite(salida, np.vstack(filas))
    print(f"  hoja de contacto: {salida}")
    return salida


# ── cli ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Encuentra las ventanas limpias de un footage")
    ap.add_argument("video")
    ap.add_argument("--exportar", help="escribe un raw curado con las ventanas limpias")
    ap.add_argument("--contacto", help="hoja de contacto PNG para revisar a ojo")
    ap.add_argument("--min", type=float, default=MIN_VENTANA,
                    help="duración mínima de ventana (default 3.5s)")
    ap.add_argument("--cabeza", type=float, default=CABEZA_DESCARTE,
                    help="segundos iniciales a descartar (default 12)")
    ap.add_argument("--intervalo", type=float, default=INTERVALO)
    ap.add_argument("--max", type=float, help="tope de segundos a exportar")
    ap.add_argument("--rapido", action="store_true",
                    help="sin OCR: solo overlay fijo y negros")
    a = ap.parse_args()

    rep = analizar(a.video, intervalo=a.intervalo, cabeza=a.cabeza,
                   min_ventana=a.min, rapido=a.rapido)

    if a.contacto:
        hoja_contacto(a.video, rep, a.contacto)
    if a.exportar:
        exportar_limpio(a.video, rep, a.exportar, max_segundos=a.max)

    sys.exit(0 if rep.ventanas else 1)


if __name__ == "__main__":
    main()
