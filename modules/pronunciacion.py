"""pronunciacion.py — Arregla nombres propios que ElevenLabs lee MAL.

El TTS a veces destroza apellidos/nombres (p.ej. "Gaitán" → "gatitán"). Aquí
vive un diccionario de reescrituras FONÉTICAS que se aplican a la NARRACIÓN
hablada ANTES de mandarla a la voz. La tarjeta/subtítulo sigue mostrando el
nombre BIEN escrito; solo cambia lo que la voz "ve".

Cómo crecer esto: cuando oigas un nombre mal pronunciado, agrega una línea a
`_REEMPLAZOS` con el nombre REAL y una reescritura que suene bien. Prueba
respellings simples (sílabas separadas, 'y' por 'i', doble vocal, etc.).
El match ignora mayúsculas y tildes, así que "Gaitan" y "Gaitán" caen igual.
"""
import re
import unicodedata

# nombre tal como se escribe  →  cómo deletrearlo para que la voz lo diga bien.
# (clave sin distinción de may/min ni tildes; el valor va tal cual a la voz)
_REEMPLAZOS = {
    "gaitan":        "Gaytán",        # Jorge Eliécer Gaitán  (el TTS decía "gatitán")
    "gaitán":        "Gaytán",
    "santander":     "Santandér",     # fuerza el acento en la última sílaba
    "bolivar":       "Bolívar",
    "bolívar":       "Bolívar",
    "uribe":         "Uríbe",
    "macondo":       "Macóndo",
    "garcia marquez": "García Márquez",
}


def _clave(s: str) -> str:
    """minúsculas sin tildes, para comparar."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


# Diccionario normalizado una sola vez (clave sin tildes → reemplazo).
_NORM = {_clave(k): v for k, v in _REEMPLAZOS.items()}

# Regex de palabras/frases a buscar (las más largas primero, para frases).
_claves_ordenadas = sorted(_REEMPLAZOS.keys(), key=len, reverse=True)
_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _claves_ordenadas) + r")\b",
    re.IGNORECASE,
) if _claves_ordenadas else None


def corregir_pronunciacion(texto: str) -> str:
    """Sustituye nombres propios problemáticos por su reescritura fonética."""
    if not texto or _RE is None:
        return texto

    def _repl(m):
        return _NORM.get(_clave(m.group(0)), m.group(0))

    return _RE.sub(_repl, texto)


if __name__ == "__main__":
    import sys
    t = " ".join(sys.argv[1:]) or "Jorge Eliécer Gaitán murió en 1948 en Bogotá."
    print(corregir_pronunciacion(t))
