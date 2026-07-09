"""num_es.py — Normaliza números para la VOZ (ElevenLabs se traba con números largos
en dígitos: "263,500" sale como garabato). Convierte los enteros grandes (≥1000) a
palabras en español ANTES de mandar el texto a TTS. Deja intactos los cortos (<1000),
los decimales (3.4, 12.7) y los porcentajes, que la voz ya lee bien.

Solo se aplica a la NARRACIÓN hablada; las tarjetas/gráficas siguen en dígitos.
"""
import re

_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
      "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
      "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
      "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_D = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_C = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
      "seiscientos", "setecientos", "ochocientos", "novecientos"]


def _centenas(n: int) -> str:            # 0..999
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    c, r = n // 100, n % 100
    out = _C[c] if c else ""
    if r:
        if out:
            out += " "
        if r < 30:
            out += _U[r]
        else:
            d, u = r // 10, r % 10
            out += _D[d] + (" y " + _U[u] if u else "")
    return out


def _miles(n: int) -> str:               # 0..999_999
    if n < 1000:
        return _centenas(n)
    m, r = n // 1000, n % 1000
    pref = "mil" if m == 1 else _centenas(m) + " mil"
    return pref + (" " + _centenas(r) if r else "")


def _entero_a_palabras(n: int) -> str:   # 0..999_999_999
    if n < 1_000_000:
        return _miles(n)
    mill, r = n // 1_000_000, n % 1_000_000
    pref = "un millón" if mill == 1 else _miles(mill) + " millones"
    return pref + (" " + _miles(r) if r else "")


# Entero con separador de miles (,) o 4+ dígitos, NO seguido de decimal (.###).
_RE_NUM = re.compile(r"\$?\d{1,3}(?:,\d{3})+(?!\.\d)|\$?\d{4,}(?!\.\d)")

# Apócope: "uno/veintiuno" → "un/veintiún" antes de un sustantivo masculino.
_RE_APOC = re.compile(
    r"\b(veinti)?uno(?=\s+(?:mil|millones|mill[oó]n|pesos|d[oó]lares|barriles|"
    r"a[ñn]os|billones|puntos)\b)")


def _apocope(texto: str) -> str:
    return _RE_APOC.sub(lambda m: ("veintiún" if m.group(1) else "un"), texto)


def normalizar_numeros_es(texto: str) -> str:
    """Deletrea a palabras los enteros ≥1000 del texto (para que la voz no se trabe)."""
    if not texto:
        return texto

    def _repl(m):
        s = m.group(0).replace("$", "").replace(",", "")
        if not s.isdigit():
            return m.group(0)
        n = int(s)
        if n < 1000:
            return m.group(0)
        return _entero_a_palabras(n)

    return _apocope(_RE_NUM.sub(_repl, texto))
