"""
run_essay.py — Pipeline de VIDEO-ENSAYO LARGO de ECONOMÍA (Profesor Gato)

Formato YouTube horizontal 16:9, 8-10 min. Dúo Gato/Bastet + tarjetas de datos
verificados (fact_checker con web search). MANUAL: NO va al scheduler; por defecto
GENERA y NO publica (Luigi revisa; se publica con --publish o ad-hoc).

NO toca el pipeline de Shorts en producción. Solo usa módulos compartidos en modo
lectura (fact_checker, background_generator, music_generator — extendidos de forma
aditiva) y escribe a videos_largos/.

USO:
  python run_essay.py "el negocio del mundial" --script-only   # ficha + guion (barato, para revisar)
  python run_essay.py "el negocio del mundial"                 # genera el video completo
  python run_essay.py "el negocio del mundial" --reuse-script audio/ESSAY_X   # guion ya aprobado → voz+render
  python run_essay.py "el negocio del mundial" --reuse-audio  audio/ESSAY_X   # re-render sin re-pagar voz
"""

import sys
import json
import logging
import re
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_essay")

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _slug(t: str) -> str:
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return re.sub(r"[\s]+", "_", t.strip())


# ── OUTLINES CURADOS (flujo híbrido: Claude propone → Luigi aprueba) ──────────
OUTLINES = {
    # La economía que hereda el nuevo presidente de Colombia (posesión 7 ago 2026).
    # Tono MEDIDO y no-partidista: Gato NO ataca a De la Espriella ni al saliente;
    # habla de los NÚMEROS que recibe cualquier gobierno que entra hoy. Engagement por
    # datos, no por bando. Cifras SOLO de la ficha verificada; lo no confirmado, como
    # pregunta. Aprovecha el nuevo visual: FOOTAGE real de la posesión/Congreso/Bogotá.
    "la economía que hereda el nuevo presidente de colombia": {
        "nota": ("El HOOK es la posesión de hoy (Abelardo de la Espriella asume como "
                 "presidente número 61 de Colombia, en Cali, con la mayor votación de la "
                 "historia). Pero el video NO opina del presidente ni de su política: "
                 "pregunta '¿qué economía recibe?'. Tono sobrio, de profesor que explica, "
                 "sin banner ni hate ni celebración. Usa footage real (tipo:footage) para "
                 "la posesión y el Congreso, fotos para Bogotá/billetes, y GRÁFICAS para "
                 "las comparaciones de cifras. NO uses 'hoy/mañana' de forma que caduque "
                 "raro: 'al asumir en 2026' está bien. Cierre lúcido, no derrotista: el "
                 "reto es real y le toca a cualquiera que gobierne."),
        "capitulos": [
            {"capitulo": "La herencia detrás de la ceremonia",
             "notas": ("hook: hoy Colombia estrena presidente 61 con la posesión en Cali; "
                       "pero detrás del protocolo hay una caja pública que recibe en cierto "
                       "estado; el video va a mirar los números fríos, no el discurso; "
                       "footage de la posesión presidencial")},
            {"capitulo": "El hueco fiscal",
             "notas": ("el gasto supera al ingreso: déficit fiscal cercano al 7% del PIB y "
                       "deuda pública alrededor del 66% del PIB (cifras que confirme la "
                       "ficha); explicar en simple qué significa gastar más de lo que entra "
                       "y por qué la deuda que sube limita al que llega; GRÁFICA de deuda")},
            {"capitulo": "El costo de la vida",
             "notas": ("inflación por encima de la meta (cerca de 6.4%, meta del 3% que no "
                       "volvería pronto) y el dólar promedio alrededor de 3.750 pesos; cómo "
                       "eso pega al bolsillo del colombiano común; CTA de mitad aquí; "
                       "footage/foto de mercado o billetes")},
            {"capitulo": "El motor que no arranca del todo",
             "notas": ("crecimiento del PIB moderado (cerca de 2.9%, revisado a la baja) y "
                       "el problema estructural del empleo informal; qué tan difícil es "
                       "crecer y crear empleo bueno con la caja apretada; GRÁFICA")},
            {"capitulo": "Lo que de verdad se hereda",
             "notas": ("cierre medido: gobierne quien gobierne, estos números son el punto "
                       "de partida; la pregunta honesta para comentar: ¿qué debería ser la "
                       "prioridad número uno con esta herencia? sin decir por quién votar")},
        ],
    },
    # El negocio del Mundial. Validado por el video TOP del canal ("boletos
    # imposibles", 756 vistas + comentarios de rabia). Indignación CON datos:
    # cada cifra sale de la ficha verificada; lo no verificado se narra como
    # pregunta. Cuidado EVERGREEN: el Mundial 2026 se menciona en presente
    # histórico (nada de "la próxima semana" ni resultados de partidos).
    "el negocio del mundial": {
        "nota": ("La promesa del título se empieza a responder en el PRIMER minuto. "
                 "Tono: indignación LEGÍTIMA con datos — nunca amargura ni 'no veas el "
                 "Mundial': el espectador AMA el fútbol, y justo por eso merece saber "
                 "quién factura con esa emoción. Cierre lúcido, no derrotista. "
                 "EVERGREEN: prohibido 'mañana'/'esta semana'/resultados de partidos; "
                 "el Mundial 2026 en México/Azteca se narra como hecho histórico."),
        "capitulos": [
            {"capitulo": "La fiesta que pagas tú",
             "notas": ("el contraste fundador: la FIFA organiza la fiesta y se lleva la "
                       "ganancia; el país anfitrión pone estadios, seguridad e "
                       "infraestructura con dinero público; cifras de ingresos del ciclo "
                       "mundialista de la FIFA vs. gasto público del anfitrión (las que "
                       "confirme la ficha)")},
            {"capitulo": "El boleto imposible",
             "notas": ("el ángulo que ya indignó a la audiencia del canal: precios "
                       "dinámicos de boletos del Mundial 2026, cuántos salarios mínimos "
                       "mexicanos cuesta ir a un partido, la reventa oficializada; el "
                       "aficionado de toda la vida viendo el estadio de su ciudad por "
                       "TV porque entrar cuesta lo que no gana en un mes")},
            {"capitulo": "La derrama que no llega",
             "notas": ("el mito de la 'derrama económica': qué prometen los gobiernos y "
                       "qué encuentran los estudios después; elefantes blancos (estadios "
                       "de mundiales pasados abandonados o subutilizados, los casos que "
                       "la ficha confirme, ej. Brasil 2014 / Sudáfrica 2010); quién paga "
                       "el mantenimiento cuando la fiesta se va; CTA de mitad al cerrar "
                       "este capítulo")},
            {"capitulo": "Los dueños del negocio",
             "notas": ("a dónde va cada peso: derechos de TV, patrocinadores, hospitalidad "
                       "corporativa; la exención de impuestos que la FIFA exige a los "
                       "países sede (si la ficha lo confirma, es LA tarjeta de datos del "
                       "video); Bastet pregunta lo que todos: '¿y por qué los países "
                       "aceptan?' — la respuesta política/emocional")},
            {"capitulo": "Tu Mundial de todos modos",
             "notas": ("aterrizaje personal: qué significa para TI — verlo claro no te "
                       "quita la fiesta, te quita la ingenuidad; la emoción es tuya y "
                       "esa no factura nadie; pregunta final para comentar (¿irías a un "
                       "partido a ese precio?)")},
        ],
    },

    # La deuda de Pemex. Regla de Luigi: DATOS REALES Y VERIFICABLES; las gráficas y
    # los números MANDAN sobre la emoción. Apolítico en la narración: se da crédito a
    # que la deuda BAJÓ (con datos) y se muestra el costo (dinero público) — "el número
    # no tiene ideología". Toda cifra sale de la ficha verificada; lo no confirmado va
    # como pregunta. EVERGREEN: 2025/2026 en presente histórico, sin "esta semana".
    "la deuda de pemex": {
        "nota": ("Formato NÚMEROS PRIMERO: cada capítulo abre con una cifra verificada y "
                 "una gráfica/tarjeta de datos, y la narración solo la explica. Tono: "
                 "lucidez fría, cero amargura, cero señalar partido — se reconoce lo que "
                 "mejoró (la deuda cayó 5 años seguidos) Y se muestra a costa de qué "
                 "(rescate con dinero público). Frase-ancla: 'el número no milita en "
                 "ningún partido'. NADA de cifra sin respaldo de la ficha; si algo no está "
                 "verificado, se dice como pregunta abierta. EVERGREEN."),
        "capitulos": [
            {"capitulo": "El número que no tiene ideología",
             "notas": ("abre con el tamaño REAL de la deuda financiera de Pemex al cierre "
                       "de 2025 (~84.5 mil millones de USD) y el hecho de que es la "
                       "petrolera más endeudada del mundo; GRÁFICA de deuda por año "
                       "(2018 ~106, pico 2020 ~113, 2024 ~98, 2025 ~84.5 mil M USD, las "
                       "que confirme la ficha). Bastet: '¿eso es mucho?' → comparar con "
                       "una petrolera privada (ej. deuda de Shell ~48 mil M USD) o con el "
                       "PIB de países pequeños, SOLO si la ficha lo respalda")},
            {"capitulo": "Cómo se llega a deber tanto",
             "notas": ("la causa estructural con datos: la producción de crudo se "
                       "desplomó (pico ~3.4 millones de barriles/día en 2004 con "
                       "Cantarell → ~1.67 millones en 2025, caída cercana al 50%) mientras "
                       "la petrolera seguía endeudándose y transfiriendo impuestos al "
                       "Estado; GRÁFICA de producción 2004→2025 (cifras de la ficha)")},
            {"capitulo": "La deuda bajó… ¿y eso?",
             "notas": ("HONESTIDAD CON DATOS: sí bajó — 5 años consecutivos, ~-13% en 2025, "
                       "el nivel más bajo en 11 años; PERO la baja viene de un rescate con "
                       "dinero público: plan de apoyo ~50 mil M USD (notas precapitalizadas "
                       "P-Cap ~12, banca de desarrollo ~13, emisión soberana ~14) + ~14 mil "
                       "M USD en el presupuesto 2026 para pagar su deuda. TARJETA DE DATOS. "
                       "Aquí se desinfla el '¡pero bajó!': el crédito es real, la fuente del "
                       "crédito es el contribuyente")},
            {"capitulo": "Quién paga la factura",
             "notas": ("aun con el rescate, Pemex siguió perdiendo dinero: ~2.6 mil M USD "
                       "en el 1T 2026 y ~61,250 millones de pesos en el 3T 2025 (cifras de "
                       "la ficha); cada dólar de rescate es dinero público que no fue a "
                       "salud, educación o infraestructura. CTA de mitad al cerrar el "
                       "capítulo")},
            {"capitulo": "El número sigue ahí",
             "notas": ("aterrizaje apolítico: la deuda creció y se rescató A TRAVÉS DE "
                       "VARIAS ADMINISTRACIONES — no es de un sexenio ni de un partido; "
                       "qué significa para TI como contribuyente; pregunta final para "
                       "comentar sin pedir que tomen bando")},
        ],
    },

    # El Mar de Aral. Origen: el PRIMER cómic del Profesor Gato (cuenta personal de
    # TikTok de Luigi) — jaló bien, ahora se vuelve largo robusto. ADN del canal:
    # una DECISIÓN ECONÓMICA (monocultivo de algodón para exportación, "oro blanco")
    # con una externalidad catastrófica. Internacional (URSS/Asia Central), no mexicano.
    # Regla Pemex: NÚMEROS PRIMERO, cada cifra de la ficha; lo no verificado va como
    # pregunta. Apolítico: no es un panfleto anti-URSS — la lección es UNIVERSAL sobre
    # ignorar el costo real de una decisión económica (aplica a cualquier país/empresa).
    # EVERGREEN: presente histórico, sin "esta semana".
    "el mar de aral": {
        "nota": ("Formato NÚMEROS PRIMERO con arco de tragedia (del cómic original): "
                 "oasis → apuesta económica → colapso → costo humano → ¿se puede revertir?. "
                 "Tono: lucidez con asombro triste, NUNCA catastrofismo hueco ni moraleja "
                 "ecologista de regaño — el villano no es 'el humano malo' sino una CUENTA "
                 "mal hecha (se contabilizó el algodón y NO el mar). Frase-ancla tipo: 'un mar "
                 "no aparece en ningún balance hasta que ya no está'. La recuperación del Aral "
                 "Norte (presa Kok-Aral) da un cierre de esperanza REAL con datos, no de "
                 "consuelo. Cada cifra sale de la ficha; si algo no está verificado, pregunta "
                 "abierta. Bastet hace las preguntas del espectador. EVERGREEN."),
        "capitulos": [
            {"capitulo": "El cuarto mar del mundo",
             "notas": ("abre con lo que SE PERDIÓ, en cifras: el Aral era el 4º lago más "
                       "grande del planeta (~68,000 km² en 1960), un oasis azul en pleno "
                       "desierto de Asia Central que sostenía una industria pesquera enorme "
                       "(~1/6 de la pesca de toda la URSS, decenas de miles de empleos, "
                       "puertos como Moynaq y Aralsk — las cifras que confirme la ficha). "
                       "FOTO real satelital de 1960. Bastet: '¿un mar, en un desierto?'")},
            {"capitulo": "La apuesta del oro blanco",
             "notas": ("la DECISIÓN económica, sin ideología: para volverse potencia "
                       "algodonera de exportación, la planificación soviética desvió los dos "
                       "ríos que alimentaban el mar (Amu Daria y Syr Daria) hacia canales de "
                       "riego gigantes (canal de Karakum) para monocultivo de algodón, el "
                       "'oro blanco'. El cálculo NO era estúpido: el algodón daba divisas; el "
                       "error fue no poner el mar en la cuenta. Bastet: '¿nadie avisó?' — se "
                       "sabía que el mar bajaría; se consideró un precio aceptable")},
            {"capitulo": "El mar que se evaporó",
             "notas": ("el colapso EN DATOS: sin ríos que lo repongan, el Aral empezó a "
                       "encogerse; GRÁFICA de superficie por año (1960 ~68,000 → 1990s → "
                       "2000s → hoy, las cifras de la ficha) y la salinidad que se disparó "
                       "(de ~10 g/L a más de 100 g/L, matando la vida) — mapas 1975/1985/1995 "
                       "como en el cómic. El mar se partió en pedazos. Aquí va la TARJETA DE "
                       "DATOS más fuerte del video: cuánto volumen perdió")},
            {"capitulo": "El polvo que enferma",
             "notas": ("el costo humano, con datos: donde hubo mar quedó el Aralkum, un "
                       "desierto NUEVO de sal y químicos (residuos de pesticidas y "
                       "fertilizantes del algodón); tormentas de polvo tóxico de millones "
                       "de toneladas al año que dañan pulmones y cultivos; la pesca colapsó a "
                       "CERO y dejó barcos oxidándose en la arena (la foto icónica de Moynaq); "
                       "salud regional golpeada (respiratorio, mortalidad infantil — solo lo "
                       "que la ficha respalde). CTA de mitad al cerrar el capítulo")},
            {"capitulo": "¿Se puede devolver un mar?",
             "notas": ("cierre con esperanza REAL y medida: Kazajistán y el Banco Mundial "
                       "construyeron la presa de Kok-Aral (~2005, costo que confirme la ficha) "
                       "y el Aral NORTE volvió a subir de nivel, bajó su sal y regresaron los "
                       "peces y algo de la pesca — el sur quedó casi perdido. La lección "
                       "universal: el mar no aparecía en ningún balance hasta que ya no "
                       "estaba; toda decisión económica tiene una factura que alguien paga "
                       "después. Pregunta final para comentar, sin moraleja de regaño")},
        ],
    },

    # La tierra en Colombia. Pedido de Luigi (colombiano): tema POLÉMICO que levante
    # pasiones, pero con el ADN del Gato — NÚMEROS PRIMERO, apolítico, mesurado. El
    # tema es la concentración de la propiedad rural (Gini de tierra ~0.87-0.89, de
    # los más altos del mundo) como raíz económica de 60 años de conflicto. NO es
    # panfleto de izquierda ni de derecha: la tierra concentrada no es ilegal, es una
    # ARITMÉTICA con consecuencias. El Gato es extranjero (no colombiano): "solo leo
    # la escritura". Cada cifra de la ficha; lo no verificado va como pregunta abierta.
    # EVERGREEN: presente histórico, sin "esta semana". Frase-ancla: "la tierra no
    # milita en ningún partido — solo obedece a quien tiene el título".
    "la tierra en colombia": {
        "nota": ("Formato NÚMEROS PRIMERO con arco: el contraste brutal → el número que "
                 "lo mide → el mapa de quién tiene qué → la paradoja del uso (vacas vs "
                 "comida) → cómo se amarró el nudo (historia) → qué significa. Tono: "
                 "lucidez fría, CERO señalar partido/gobierno, cero regaño ideológico — "
                 "se reconoce que concentrar tierra no es un delito y que el problema es "
                 "estructural y viejo (atraviesa TODOS los gobiernos). Frase-ancla: 'la "
                 "tierra no vota, no milita — solo obedece a quien tiene el título'. El "
                 "Gato aclara que él es extranjero: no defiende bando, solo lee cifras. "
                 "Bastet hace las preguntas del espectador ('¿el 1% tiene el 81%?'). "
                 "NADA de cifra sin respaldo de la ficha; si algo no está verificado, se "
                 "dice como pregunta. Foco Colombia pero lección universal (quién tiene "
                 "la tierra tiene el poder). EVERGREEN."),
        "capitulos": [
            {"capitulo": "Una vaca y una familia",
             "notas": ("COLD OPEN con el contraste que duele, en cifras: en Colombia el "
                       "~1% de las fincas más grandes concentra alrededor del 81% de la "
                       "tierra rural, mientras cerca del 65% de los predios miden menos de "
                       "3 hectáreas (cifras de la ficha, IGAC/Oxfam). Imagen mental: una "
                       "res de ganadería extensiva ocupa más tierra que una familia "
                       "campesina entera. FOTO real de paisaje rural colombiano (sabana/ "
                       "altiplano) o latifundio ganadero. Bastet: '¿el 1% tiene el 81%? "
                       "¿de un país entero?' — el Gato: 'no es opinión, es el catastro'")},
            {"capitulo": "El número que no vota",
             "notas": ("qué es el coeficiente de Gini (0 = todos tienen igual, 1 = uno "
                       "solo lo tiene todo) y por qué aquí importa. La tierra en Colombia "
                       "tiene un Gini de ~0.87 (frontera agrícola) a ~0.89 (predios "
                       "privados totales), IGAC 2023 — de los más altos del mundo. "
                       "CLAVE del capítulo: compararlo con el Gini de INGRESO del país "
                       "(~0.55), que ya es alto → la TIERRA está mucho MÁS concentrada que "
                       "el dinero. GRÁFICA de barras en misma escala 0-1: 'Gini del "
                       "INGRESO ~0.55' vs 'Gini de la TIERRA ~0.87'. Frase: 'la tierra es "
                       "la desigualdad que está debajo de la desigualdad'. fondo "
                       "situacional: oficina de catastro / mapa rural")},
            {"capitulo": "El mapa de quién tiene qué",
             "notas": ("la concentración con números duros: el ~1% de los mayores "
                       "propietarios posee cerca del 47% del área rural privada; el 10% "
                       "más grande, alrededor del 81%. Del otro lado, la gran mayoría de "
                       "propietarios (~80%) apenas tiene ~10% de la tierra. GRÁFICA de "
                       "barras: '% del área que tiene el top 1%' (~47), 'el top 10%' (~81) "
                       "y 'el 80% restante de dueños' (~10) — cifras de la ficha. Idea: "
                       "'no es que falte tierra; es que sobra concentrada'. fondo "
                       "situacional distinto: vista aérea de fincas/parcelas")},
            {"capitulo": "La paradoja de la vaca",
             "notas": ("el giro ECONÓMICO menos obvio (uso del suelo): Colombia dedica "
                       "~38.5 millones de hectáreas a ganadería, pero solo ~19.3 millones "
                       "tienen vocación ganadera — casi el DOBLE de lo que debería; y cerca "
                       "del 65% de la tierra apta para agricultura no se cultiva (cifras de "
                       "la ficha, IGAC/UPRA). Mientras tanto, ~70% de los alimentos que "
                       "come el país los producen mini/microfundios. GRÁFICA de barras: "
                       "'hectáreas EN ganadería ~38.5M' vs 'hectáreas CON vocación "
                       "ganadera ~19.3M'. Frase: 'la mejor tierra no está sembrada: está "
                       "pastando'. fondo situacional: potrero extenso con ganado")},
            {"capitulo": "Cómo se amarró el nudo",
             "notas": ("la historia SIN señalar partido, para explicar por qué sigue así: "
                       "1936 la Ley 200 intentó que 'la tierra fuera de quien la trabaja' "
                       "y chocó con los terratenientes; 1961 otro intento (Ley 135); en "
                       "1972 el Pacto de Chicoral frenó la reforma agraria (se le llamó "
                       "'el funeral de la reforma'). La tierra sin repartir fue una de las "
                       "raíces económicas del conflicto armado — y la guerra CONCENTRÓ aún "
                       "más por el despojo: el Gini de propietarios subió de ~0.84 (1960) a "
                       "~0.885 (2009) (Ibáñez-Muñoz/Oxfam). En 2016 el punto 1 del Acuerdo "
                       "de Paz (Reforma Rural Integral) prometió un Fondo de Tierras de 3 "
                       "millones de ha + formalizar 7 millones; años después sigue en buena "
                       "parte pendiente (sin culpar a un gobierno puntual). TARJETA/GRÁFICA "
                       "opcional: Gini de propietarios 1960 (~0.84) vs 2009 (~0.885), 'subió "
                       "con la guerra'. CTA de mitad al cerrar el capítulo")},
            {"capitulo": "La escritura sigue ahí",
             "notas": ("aterrizaje apolítico: la concentración de la tierra no es de un "
                       "gobierno ni de un partido — atravesó liberales, conservadores y a "
                       "todos los que vinieron después; es de las más viejas del país. No "
                       "se trata de odiar al que tiene tierra, sino de ver la aritmética: "
                       "quien tiene la tierra tiene el poder, y un país que produce el 70% "
                       "de su comida en pedacitos mientras su mejor suelo engorda vacas "
                       "está dejando comida, empleo y paz sobre la mesa. El Gato recuerda "
                       "que él solo leyó la escritura. Pregunta final para comentar sin "
                       "pedir que tomen bando")},
        ],
    },

    # Nicaragua deja de tener elecciones. DISPARADOR (verificado por web el 21 jul 2026):
    # el 19-20 de julio de 2026, en el acto por el 47º aniversario de la revolución
    # sandinista en Managua, Daniel Ortega —co-presidente junto a Rosario Murillo desde
    # febrero de 2025— dijo que "aquí no volverá a haber elecciones" y anunció que la
    # Asamblea Nacional aprobará leyes para "poner un muro" a la oposición. Es la primera
    # vez que lo dice en público. Fuentes: CNN en Español, Infobae, Confidencial,
    # Al Jazeera (20-21 jul 2026).
    # REGLA DEL CANAL: el Gato es INTERNACIONAL (no mexicano). Tema político delicado →
    # el video explica el MECANISMO (cómo se desmonta una democracia por la vía legal),
    # no reparte insultos: la fuerza está en los hechos y las fechas, no en el adjetivo.
    # EVERGREEN: todo con fecha explícita ("el 19 de julio de 2026"), nunca "esta semana".
    "nicaragua sin elecciones": {
        "nota": ("Formato EXPLICADOR CON LÍNEA DE TIEMPO: el video responde una sola "
                 "pregunta — ¿cómo llega un país a que su gobernante anuncie, en voz "
                 "alta, que no volverá a haber elecciones? Se cuenta como un MECANISMO "
                 "en pasos, cada uno con fecha y cifra verificada, porque el punto "
                 "didáctico es que ninguno de esos pasos fue un golpe de Estado: todos "
                 "fueron legales, votados y publicados en el diario oficial. Tono: "
                 "lucidez fría y didáctica, CERO insulto y CERO bando — no se trata de "
                 "izquierda contra derecha (el propio Ortega llegó derrocando a una "
                 "dictadura de derecha en 1979, y ese es el dato más incómodo del "
                 "video). Frase-ancla: 'las democracias ya no se caen de un golpe: se "
                 "desmontan pieza por pieza, y con papeles en regla'. NADA de cifra sin "
                 "respaldo de la ficha; lo no verificado va como pregunta abierta. "
                 "EVERGREEN: toda referencia temporal con fecha explícita. Bastet hace "
                 "las preguntas del espectador que no sigue el tema."),
        "capitulos": [
            {"capitulo": "La frase",
             "notas": ("abre en seco con el hecho: el 19 de julio de 2026, en el acto "
                       "por el 47º aniversario de la revolución sandinista en Managua, "
                       "Daniel Ortega dijo que en Nicaragua 'no volverá a haber "
                       "elecciones', y anunció que la Asamblea Nacional aprobará leyes "
                       "para 'poner un muro' a la oposición. Lo excepcional no es que "
                       "las elecciones ya no sirvieran para cambiar de gobierno —eso "
                       "llevaba años— sino que se diga en público y de frente. Bastet: "
                       "'¿un presidente puede simplemente decir eso?' → el video "
                       "responde que sí, y explica cómo se llega ahí")},
            {"capitulo": "El que derrocó a una dictadura",
             "notas": ("el contexto que casi nadie recuerda y que vuelve el tema "
                       "universal: Ortega llegó al poder en 1979 como parte de la "
                       "revolución sandinista que derrocó a la dictadura de la familia "
                       "Somoza, que llevaba más de cuatro décadas en el poder. Gobernó "
                       "en los ochenta, PERDIÓ una elección en 1990 y entregó el poder. "
                       "Volvió a ganar en 2006 y desde 2007 no ha vuelto a soltarlo. "
                       "GRÁFICA: años en el poder (dinastía Somoza vs. Ortega), con las "
                       "cifras que confirme la ficha. La lección no es sobre una "
                       "ideología: es sobre lo que le pasa a cualquiera que se queda "
                       "demasiado tiempo")},
            {"capitulo": "Los pasos legales",
             "notas": ("EL CORAZÓN DIDÁCTICO: el mecanismo, paso por paso y con fechas, "
                       "SOLO con lo que confirme la ficha — la resolución judicial de "
                       "2009/reforma que habilitó la reelección indefinida; las "
                       "elecciones de 2021 con los principales precandidatos "
                       "opositores detenidos ANTES de la votación; la reforma "
                       "constitucional que entró en vigor en 2025 y creó la figura de "
                       "'co-presidencia' (Ortega y su esposa Rosario Murillo) y estiró "
                       "el mandato de 5 a 6 años. Insistir en el patrón: cada paso fue "
                       "aprobado por instituciones formalmente válidas. CTA de mitad al "
                       "cerrar el capítulo")},
            {"capitulo": "El costo en gente",
             "notas": ("que no se quede en abstracto: las protestas de abril de 2018 y "
                       "el número de muertos que documentaron los organismos de derechos "
                       "humanos; los nicaragüenses que salieron del país desde entonces; "
                       "los opositores a los que se les retiró la nacionalidad y se "
                       "declaró 'apátridas'; medios y organizaciones civiles cerrados. "
                       "GRÁFICA con la serie que confirme la ficha (muertos 2018, "
                       "personas desnacionalizadas, ONG canceladas o emigración). "
                       "Bastet pregunta '¿y nadie hizo nada?' → la respuesta honesta "
                       "sobre sanciones y condenas internacionales y su límite real")},
            {"capitulo": "Por qué te importa aunque no seas de ahí",
             "notas": ("aterrizaje universal y apolítico, el que convierte: esto no es "
                       "una nota exótica sobre un país chico. El manual se repite —en "
                       "América Latina, en Europa del Este, en África— y siempre empieza "
                       "igual: no con tanques, sino con reformas que se ven aburridas, "
                       "tribunales que dan la razón y elecciones que se siguen "
                       "celebrando hasta que dejan de significar algo. La señal de "
                       "alarma nunca es el día que las cancelan; es el día que dejan de "
                       "poder cambiar nada. Cerrar sin pedir que tomen bando y con "
                       "pregunta abierta para comentarios")},
        ],
    },

    # El negocio de GTA VI. Pedido de Luigi para montar la ola de búsqueda del
    # adelanto de agosto de 2026 (tráiler extendido en Netflix, 27 ago) y del
    # lanzamiento previsto para el 19 de noviembre de 2026. Tema NO político: puro
    # negocio y cultura. ADN del Gato: NÚMEROS PRIMERO, asombro LÚCIDO (admira la
    # máquina de dinero sin volverse fanboy ni sermonear). El presupuesto de GTA VI
    # es RUMOR/ESTIMACIÓN (Rockstar no lo confirma) → SIEMPRE se narra como "se
    # estima / los analistas calculan", nunca como hecho. Frase-ancla: "no es un
    # juego que factura como una película; es una película que ninguna película
    # podría pagar". Aprovecha el visual nuevo: FOOTAGE del tráiler oficial en el
    # hook y en el capítulo del presupuesto (ojo: NO es Creative Commons, decisión
    # de Luigi de asumir el Content ID), GRÁFICAS para las comparaciones de dinero,
    # pixel-art para lo demás. EVERGREEN con fechas EXPLÍCITAS ("el adelanto de
    # agosto de 2026", "el lanzamiento previsto para el 19 de noviembre de 2026");
    # prohibido "esta semana/mañana". Cada cifra sale de la ficha verificada.
    "el negocio de gta vi": {
        "nota": ("Formato NÚMEROS PRIMERO sobre un tema de NEGOCIO (no político). "
                 "Tono: asombro lúcido y un punto cínico de buen gusto — el Gato "
                 "admira la maquinaria financiera de GTA sin venderse a ella y sin "
                 "regañar al que ama el juego (el espectador AMA GTA; justo por eso "
                 "merece ver quién factura con esa emoción). El presupuesto de GTA VI "
                 "es ESTIMACIÓN de analistas/medios, NO cifra oficial → decirlo así "
                 "cada vez ('se estima', 'los analistas calculan'); lo confirmado (lo "
                 "de GTA V) va como hecho duro. Frase-ancla: 'no es un juego que "
                 "factura como una película; es una película que ninguna película "
                 "podría pagar'. EVERGREEN con fechas explícitas: el adelanto se ubica "
                 "'en agosto de 2026' y el lanzamiento 'previsto para el 19 de "
                 "noviembre de 2026'; PROHIBIDO 'esta semana/mañana' o spoilers de "
                 "gameplay. Footage del tráiler oficial en el hook y en el capítulo "
                 "del presupuesto; gráficas para el dinero; Bastet hace las preguntas "
                 "del jugador. Cada cifra sale de la ficha verificada."),
        "capitulos": [
            {"capitulo": "El producto más caro jamás hecho",
             "notas": ("hook con la cifra: se ESTIMA que GTA VI costó entre 1 y 2 mil "
                       "millones de dólares entre desarrollo y marketing (cifra de "
                       "analistas/medios, NO confirmada por Rockstar — decirlo así), lo "
                       "que lo volvería el producto de entretenimiento más caro jamás "
                       "producido, por encima de cualquier película de Hollywood; "
                       "comparar con lo que confirme la ficha. FOOTAGE del tráiler "
                       "oficial de GTA VI. Bastet: '¿un videojuego cuesta más que una "
                       "película de Marvel?' — el Gato: 'y ni siquiera es la parte "
                       "impresionante'")},
            {"capitulo": "Cómo un juego factura más que Hollywood",
             "notas": ("la PRUEBA con GTA V (cifras duras, ya confirmadas): recaudó "
                       "alrededor de 8-9 mil millones de USD y vendió más de 200 "
                       "millones de copias, volviéndose uno de los productos de "
                       "entretenimiento más rentables de la historia; hizo cerca de "
                       "1,000 millones de USD en sus primeros 3 días. GRÁFICA de barras "
                       "comparando ingresos de GTA V contra las películas más "
                       "taquilleras de la historia (Avatar ~2.9 mil M, Avengers Endgame "
                       "~2.8 mil M — las que confirme la ficha). fondo situacional: "
                       "estreno de cine / alfombra roja vs pantalla de juego")},
            {"capitulo": "El dinero no está donde crees",
             "notas": ("el MODELO real, el giro didáctico: el grueso del dinero no está "
                       "en vender el juego una vez a 60-70 dólares, sino en GTA Online y "
                       "los micropagos (las 'Shark Cards'); el gasto recurrente del "
                       "jugador ('recurrent consumer spending') es la mayor parte de las "
                       "reservas de Take-Two año tras año (el % que confirme la ficha). "
                       "TARJETA/GRÁFICA de datos. Idea-ancla: 'el juego es el anzuelo; "
                       "la tienda dentro del juego es el negocio'. Bastet: '¿o sea que "
                       "pago el juego y encima sigo pagando?'")},
            {"capitulo": "La apuesta de dos mil millones",
             "notas": ("el RIESGO y la ambición: Take-Two (dueña de Rockstar) tiene "
                       "buena parte de su valor de bolsa amarrado a este lanzamiento; el "
                       "juego se retrasó y quedó previsto para el 19 de noviembre de "
                       "2026 (PS5 y Xbox Series); los analistas calculan que podría ser "
                       "el lanzamiento de entretenimiento más grande de la historia y "
                       "hasta mover el gasto de consumo de un trimestre (cifras/citas de "
                       "la ficha, marcadas como proyección). FOOTAGE del tráiler. "
                       "GRÁFICA opcional: capitalización de Take-Two o proyección de "
                       "ventas. CTA de mitad al cerrar el capítulo")},
            {"capitulo": "Tú eres el negocio",
             "notas": ("aterrizaje: la industria del videojuego ya factura más que el "
                       "cine y la música juntos (cifra de la ficha); el verdadero motor "
                       "de GTA no es Rockstar, eres tú y tus horas. Verlo claro no te "
                       "quita las ganas de jugarlo — te quita la ingenuidad; la emoción "
                       "de jugar es tuya y esa no la cobra nadie. Pregunta final para "
                       "comentar: ¿solo comprarías el juego base, o entrarías a los "
                       "micropagos de GTA Online?")},
        ],
    },

    # El terremoto de Colombia (10 ago 2026). Pedido de Luigi, colombiano que lo vive
    # DESDE AFUERA (su gente está bien, quedó el susto). Tema SENSIBLE: hay muertos en
    # su país el mismo día → el video INFORMA y HONRA, no farmea la tragedia; abre
    # reconociendo el luto y las cifras como PRELIMINARES a la fecha. Enfoque elegido:
    # CIENCIA → ECONOMÍA (por qué un sismo profundo en Chocó rompió el Eje Cafetero, y
    # aterriza en el costo de reconstruir + la sismorresistencia como prevención que
    # sale más barata). ADN del Gato: NÚMEROS PRIMERO, lucidez didáctica, CERO
    # catastrofismo hueco y CERO show. El Gato es extranjero: habla con respeto y
    # solidaridad ("esta vez el número duele más"), sin fingir que es colombiano.
    # OJO CIFRAS: el balance de víctimas/daños SIGUE SUBIENDO — refrescar el fact-check
    # justo antes del render y narrar SIEMPRE "cifras preliminares al [fecha]". Lo
    # verificable y estable (el sismo del Eje Cafetero de 1999, la norma NSR-10, la
    # ciencia de la profundidad) es el esqueleto duro del video.
    "el terremoto de colombia": {
        "nota": ("Tema SENSIBLE y RECIENTE (hay víctimas). Tono: respeto y lucidez "
                 "didáctica, NUNCA morbo ni catastrofismo ni 'mira qué fuerte' — el "
                 "punto es ENTENDER (por qué pasó, por qué unos lugares sufren más, "
                 "cuánto cuesta y cómo se previene), no espectacular con el dolor. Abre "
                 "reconociendo la pérdida humana y que las cifras son PRELIMINARES a la "
                 "fecha (se narran como 'al menos, hasta el [día]'); NADA de cifra de "
                 "víctimas afirmada como definitiva. El Gato es EXTRANJERO: acompaña con "
                 "respeto y solidaridad, sin fingir nacionalidad. Estructura CIENCIA → "
                 "ECONOMÍA: 1) qué pasó, 2) por qué se sintió tan lejos (profundidad), "
                 "3) por qué unas ciudades sufren más (suelo + construcción), 4) cuánto "
                 "cuesta un terremoto (con el Eje Cafetero 1999 como referencia dura y "
                 "verificable), 5) por qué prevenir sale más barato (NSR-10). Frase-"
                 "ancla: 'la factura de un terremoto se paga antes, previniendo, o "
                 "después, reconstruyendo — pero siempre se paga'. Cada cifra sale de la "
                 "ficha; lo no verificado va como pregunta. Cierre digno y de esperanza "
                 "REAL (Colombia se levantó del 99), no consuelo hueco. Bastet hace las "
                 "preguntas del espectador."),
        "capitulos": [
            {"capitulo": "El país que tembló entero",
             "notas": ("abre con respeto y con el hecho, en cifras verificadas: el 10 de "
                       "agosto de 2026, a las 7:34 de la mañana, un sismo de magnitud 7.4 "
                       "con epicentro en San José del Palmar (Chocó, occidente de "
                       "Colombia) se sintió en Bogotá, Medellín, Cali, Pereira, Manizales "
                       "y hasta en Ecuador y Panamá. Reconocer el luto y que el balance "
                       "de víctimas es PRELIMINAR y sigue actualizándose. La pregunta "
                       "rara que abre el video: el epicentro estaba en Chocó, pero varios "
                       "de los peores daños se vieron a cientos de kilómetros, en el Eje "
                       "Cafetero. FOTO/FOOTAGE real (daños, la Catedral de Manizales). "
                       "Bastet: '¿cómo un temblor en Chocó agrieta edificios en "
                       "Manizales?'")},
            {"capitulo": "Por qué se sintió tan lejos",
             "notas": ("LA CIENCIA, en simple: fue un sismo PROFUNDO (unos 80–110 km, la "
                       "cifra que confirme la ficha), no superficial. Un sismo profundo "
                       "libera su energía muy abajo y esa energía alcanza a sacudir un "
                       "área ENORME —países enteros— aunque en el epicentro el daño en "
                       "superficie sea menor; uno superficial destruye local pero se "
                       "siente menos lejos. La causa tectónica: la placa de Nazca se "
                       "hunde (subducción) bajo Sudamérica y el sismo ocurre dentro de "
                       "esa placa hundida (verificar el mecanismo exacto en la ficha). "
                       "GRÁFICA/esquema: profundidad vs. área sentida. Bastet: '¿entre "
                       "más profundo, más lejos se siente?'")},
            {"capitulo": "Por qué unas ciudades sí y otras no",
             "notas": ("el puente hacia lo económico: el daño NO lo decide solo el sismo, "
                       "lo deciden el SUELO y la CONSTRUCCIÓN. Efecto de sitio: ciudades "
                       "sobre suelos blandos o en laderas (Manizales, Pereira, Armenia) "
                       "amplifican la sacudida; y las construcciones viejas o informales "
                       "colapsan donde una sismorresistente aguanta. Idea-ancla: 'el "
                       "terremoto no mata; matan los edificios mal hechos'. FOTO de daño "
                       "estructural real. Esto prepara la pregunta del dinero: ¿cuánto "
                       "cuesta construir bien vs. reconstruir después?")},
            {"capitulo": "Cuánto cuesta un terremoto",
             "notas": ("el costo económico con el ANCLA verificable y estable: el "
                       "terremoto del Eje Cafetero de 1999 (Armenia, magnitud ~6.2) dejó "
                       "más de 1.000 muertos y un costo de reconstrucción del orden de "
                       "1.500–2.800 millones de USD, cerca del 1.5–2% del PIB de entonces "
                       "(las cifras que confirme la ficha; se creó el FOREC para "
                       "manejarlo). Un terremoto golpea el PIB regional, destruye capital "
                       "de años y la mayoría de las viviendas NO está asegurada (brecha "
                       "de aseguramiento, dato de la ficha). GRÁFICA de costos. CTA de "
                       "mitad al cerrar el capítulo")},
            {"capitulo": "Por qué prevenir sale más barato",
             "notas": ("la lección económica universal y útil: tras el 99, Colombia "
                       "endureció su norma sismorresistente (NSR-98 → NSR-10); construir "
                       "sismorresistente encarece la obra un poco, pero cada peso puesto "
                       "en prevención/mitigación ahorra varios en reconstrucción y "
                       "rescate (la relación que confirme la ficha, tipo 1 a 4–7). "
                       "Reforzar lo viejo (retrofit) y los sistemas de alerta también "
                       "pagan. Frase-ancla: 'la factura se paga antes o después, pero "
                       "siempre se paga'. GRÁFICA opcional: costo prevenir vs. costo "
                       "reconstruir")},
            {"capitulo": "Colombia se levanta",
             "notas": ("cierre DIGNO, con esperanza real y datos, no consuelo hueco: "
                       "Colombia ya se levantó del Eje Cafetero en 1999 y aprendió (por "
                       "eso hoy hay norma); la tierra no avisa, pero la matemática de la "
                       "prevención sí. El Gato, extranjero, cierra con respeto y "
                       "solidaridad con Colombia. Pregunta final para comentar SIN morbo "
                       "(ej. ¿tu casa/edificio sabes si es sismorresistente? / qué debería "
                       "priorizar un país sísmico), invitando a una conversación útil")},
        ],
    },
}

# Enfoque de búsqueda del fact_checker por tema (qué cifras necesita el guion).
FICHA_ENFOQUE = {
    "el terremoto de colombia": (
        "- El sismo del 10 de agosto de 2026 en Colombia: magnitud oficial (Servicio "
        "Geológico Colombiano y USGS), hora local, epicentro (San José del Palmar, "
        "Chocó) y PROFUNDIDAD exacta en km\n"
        "- Ciudades y países donde se sintió (Bogotá, Medellín, Cali, Pereira, "
        "Manizales, Quibdó; Ecuador, Panamá) y el dato de daños en el Eje Cafetero pese "
        "a estar lejos del epicentro\n"
        "- Balance PRELIMINAR de víctimas y daños con FECHA de corte (dejar claro que es "
        "provisional y sigue actualizándose): muertos, heridos, edificaciones "
        "colapsadas, la Catedral de Manizales, aeropuertos afectados, réplicas\n"
        "- CIENCIA: por qué un sismo PROFUNDO (intraplaca/intraslab) se percibe en un "
        "área mucho más amplia que uno superficial; el mecanismo tectónico del occidente "
        "colombiano (subducción de la placa de Nazca / bloque Panamá-Chocó)\n"
        "- Efecto de sitio: por qué ciudades como Manizales, Pereira y Armenia (suelos "
        "blandos, laderas) amplifican la sacudida\n"
        "- Terremoto del Eje Cafetero (Armenia/Quindío) del 25 de enero de 1999: "
        "magnitud (~6.2), número de muertos (~1.000+), costo de reconstrucción en USD "
        "(~1.500–2.800 millones), su peso como % del PIB de entonces y el papel del FOREC\n"
        "- Norma sismorresistente colombiana: NSR-98 tras el 99 y la vigente NSR-10 "
        "(qué exige, cuándo entró)\n"
        "- Brecha de aseguramiento en Colombia: % de viviendas aseguradas contra "
        "terremoto (o penetración del seguro), cifra reciente\n"
        "- Relación costo-beneficio de la prevención sísmica: cuánto ahorra en "
        "reconstrucción/rescate cada dólar invertido en mitigación (estudios tipo "
        "BID/Banco Mundial/UNDRR), y el sobrecosto aproximado de construir sismorresistente"
    ),
    "el negocio de gta vi": (
        "- Presupuesto ESTIMADO de desarrollo + marketing de GTA VI: el rango que "
        "reportan analistas y medios (p. ej. 1,000 a 2,000 millones de USD), dejando "
        "CLARO que es estimación no confirmada por Rockstar/Take-Two; y si sería el "
        "producto de entretenimiento más caro jamás producido\n"
        "- Fecha de lanzamiento de GTA VI (19 de noviembre de 2026) y plataformas "
        "(PlayStation 5 y Xbox Series X/S)\n"
        "- Ingresos totales acumulados de GTA V hasta 2025/2026 (estimación en USD, "
        "del orden de 8-9 mil millones) y copias vendidas (más de 200 millones)\n"
        "- Récord de lanzamiento de GTA V: cuánto facturó en sus primeros 3 días "
        "(~1,000 millones de USD) y en su primera semana\n"
        "- Costo de desarrollo + marketing de GTA V (~265 millones de USD) para "
        "contrastar con la estimación de GTA VI\n"
        "- Película más taquillera de la historia (Avatar ~2.9 mil M USD) y otra "
        "referencia (Avengers: Endgame ~2.8 mil M USD) para comparar con GTA V\n"
        "- Ingreso por gasto recurrente del jugador / GTA Online / microtransacciones "
        "('recurrent consumer spending') de Take-Two: cifra anual o % de sus reservas "
        "netas\n"
        "- Capitalización de mercado de Take-Two Interactive y qué tanto de su "
        "valuación y expectativa de analistas depende de GTA VI\n"
        "- Tamaño de la industria global de videojuegos en ingresos y comparación con "
        "el cine (taquilla mundial) y la música juntos\n"
        "- Proyecciones de analistas sobre ventas de GTA VI (día uno, primer mes o "
        "primer año), marcadas como proyección"
    ),
    "nicaragua sin elecciones": (
        "- La declaración de Daniel Ortega del 19 de julio de 2026 en el acto por el 47º "
        "aniversario de la revolución sandinista: cita textual de que 'no volverá a haber "
        "elecciones' y el anuncio de leyes de la Asamblea Nacional para bloquear a la "
        "oposición (fuente y fecha exactas)\n"
        "- Cronología del poder de Ortega: llegada en 1979 (caída de la dictadura de "
        "Somoza), gobierno de los ochenta, derrota electoral de 1990 y entrega del poder, "
        "regreso en 2006/2007; total de años que la familia Somoza estuvo en el poder vs. "
        "años acumulados de Ortega — para una gráfica comparativa\n"
        "- La reforma constitucional que entró en vigor en 2025: figura de 'co-presidencia' "
        "(Ortega y Rosario Murillo) y extensión del mandato presidencial de 5 a 6 años "
        "(fecha y contenido)\n"
        "- La reelección indefinida: resolución/reforma que la habilitó (año) \n"
        "- Elecciones de 2021: número de precandidatos opositores detenidos antes de los "
        "comicios y % oficial con que ganó Ortega\n"
        "- Protestas de abril de 2018: número de muertos según organismos de derechos "
        "humanos (CIDH/ONU), cifra de personas que han emigrado de Nicaragua desde 2018\n"
        "- Opositores a los que se retiró la nacionalidad ('apátridas'): número de "
        "personas desnacionalizadas; ONG y medios cerrados por el gobierno\n"
        "- Sanciones o condenas internacionales relevantes (OEA, UE, EE.UU.) y su alcance"
    ),
    "el negocio del mundial": (
        "- Ingresos de la FIFA en el ciclo del Mundial 2026 (proyección o cifra oficial)\n"
        "- Ingresos reales de la FIFA en el ciclo de Qatar 2022\n"
        "- Precios de boletos del Mundial 2026 (rango, precios dinámicos) y salario "
        "mínimo mensual en México 2026\n"
        "- Gasto público de México/sedes en estadios e infraestructura para 2026\n"
        "- Exención de impuestos que la FIFA exige a países sede (¿aplica en México 2026?)\n"
        "- Estudios sobre 'derrama económica' real de mundiales pasados vs. lo prometido\n"
        "- Elefantes blancos: estadios de Brasil 2014 / Sudáfrica 2010 hoy\n"
        "- Reparto: cuánto de los ingresos viene de derechos de TV y patrocinios"
    ),
    "la deuda de pemex": (
        "- Deuda financiera de Pemex al cierre de 2025 (cifra oficial en USD) y su nivel "
        "en 2024, 2020 (pico) y 2018, para una serie por año\n"
        "- Confirmación de si Pemex es la petrolera (o corporativo no financiero) más "
        "endeudado del mundo, y una referencia de deuda de una petrolera privada (Shell/Exxon)\n"
        "- Producción de crudo de Pemex: pico de 2004 (Cantarell) y nivel actual "
        "(2025) en barriles por día, y % de caída\n"
        "- Rescate/apoyo del gobierno a Pemex: monto del plan estratégico 2025 y su "
        "desglose (notas precapitalizadas/P-Cap, banca de desarrollo, emisión soberana)\n"
        "- Monto en el presupuesto federal 2026 destinado a pagar deuda de Pemex\n"
        "- Pérdidas recientes de Pemex: resultado del 1T 2026 y del 3T 2025\n"
        "- Meta de deuda del Plan Pemex hacia 2030"
    ),
    "el mar de aral": (
        "- Superficie del Mar de Aral en 1960 (~km²) y su lugar como uno de los lagos "
        "más grandes del mundo (¿4º?)\n"
        "- Serie de superficie y/o volumen por año para una gráfica: 1960, 1975, 1985, "
        "1995, 2000s y nivel actual (km² o % perdido)\n"
        "- Salinidad del agua: nivel original (~g/L) vs. actual, y su efecto en la vida\n"
        "- Los dos ríos desviados (Amu Daria y Syr Daria), el canal de Karakum y la "
        "expansión del algodón de exportación soviético/uzbeko (superficie regada o "
        "producción de algodón, si hay cifra)\n"
        "- Industria pesquera del Aral: captura anual en su pico, empleos y su "
        "participación en la pesca de la URSS; colapso a cero (puertos de Moynaq/Aralsk)\n"
        "- El desierto Aralkum: superficie del lecho seco y volumen de tormentas de "
        "polvo salino/tóxico al año\n"
        "- Impactos de salud en la región (respiratorios, mortalidad infantil), solo "
        "cifras verificables\n"
        "- Recuperación del Aral Norte: presa de Kok-Aral (año ~2005), costo y "
        "financiamiento (Banco Mundial), y el rebote de nivel/pesca reportado"
    ),
    "la tierra en colombia": (
        "- Coeficiente de Gini de la TIERRA/propiedad rural en Colombia según el estudio "
        "más reciente del IGAC (2023): valor para la frontera agrícola (~0.87) y para los "
        "predios rurales privados totales (~0.89), y su lugar entre los más altos del mundo\n"
        "- Coeficiente de Gini del INGRESO de Colombia reciente (~0.55) para contraste, y "
        "su posición en América Latina / el mundo\n"
        "- Concentración: % del área rural privada en manos del 1%, 5% y 10% de los mayores "
        "propietarios (~47%, ~71%, ~81%); % de predios menores a 3 hectáreas (~65%); % de "
        "propietarios pequeños y la fracción de tierra que tienen (~80% de dueños con ~10%)\n"
        "- Oxfam / Semana: '1% de las fincas más grandes controla ~81% de la tierra'\n"
        "- Uso del suelo: hectáreas dedicadas a ganadería (~38.5M) vs hectáreas con vocación "
        "ganadera (~19.3M); % de la tierra apta para agricultura que no se aprovecha (~65%)\n"
        "- % de los alimentos del país producidos por minifundio/microfundio (~70%)\n"
        "- Historia agraria: Ley 200 de 1936, Ley 135 de 1961, Pacto de Chicoral 1972 (qué "
        "frenó); evolución del Gini de propietarios 1960 (~0.84) → 2009 (~0.885) (Ibáñez-Muñoz)\n"
        "- Acuerdo de Paz 2016, punto 1 (Reforma Rural Integral): Fondo de Tierras de 3 "
        "millones de ha + formalización de 7 millones de ha, y estado de avance (sin señalar "
        "partido/gobierno)"
    ),
}


# Footage que se baja del canal OFICIAL saltando el filtro Creative Commons
# (material bajo riesgo propio de Content ID — decisión explícita de Luigi). Cada
# entrada: subcadena que debe aparecer en la query del visual -> canal oficial a
# preferir. Todo lo que NO caiga aquí sigue por la vía Creative Commons segura.
FOOTAGE_OFICIAL = {
    "gta vi official trailer": "Rockstar Games",
    "gta 6 official trailer": "Rockstar Games",
    "gta vi trailer": "Rockstar Games",
    "gta 6 trailer": "Rockstar Games",
}


def _canal_oficial_para(query: str) -> str | None:
    q = (query or "").lower()
    for sub, canal in FOOTAGE_OFICIAL.items():
        if sub in q:
            return canal
    return None


def banner(t):
    log.info("=" * 60); log.info(f"  {t}"); log.info("=" * 60)


def _cargar_audios_existentes(carpeta: str, segmentos: list[dict]) -> list[dict]:
    """Reusa voz ya generada (bloque_*.mp3 + palabras.json) sin re-pagar ElevenLabs."""
    from modules.essay_voice import obtener_duracion_audio
    carpeta = Path(carpeta)
    mp3s = sorted(carpeta.glob("bloque_*.mp3"))
    if not mp3s:
        raise RuntimeError(f"No hay bloque_*.mp3 en {carpeta}")
    palabras_map = {}
    pj = carpeta / "palabras.json"
    if pj.exists():
        try:
            palabras_map = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            palabras_map = {}
    audios = []
    for i, p in enumerate(mp3s, 1):
        speaker = segmentos[i - 1].get("speaker", "gato") if i <= len(segmentos) else "gato"
        audios.append({"numero": i, "speaker": speaker, "ruta_audio": str(p),
                       "duracion_real": obtener_duracion_audio(str(p)),
                       "palabras": palabras_map.get(str(i), [])})
    log.info(f"  Reusando {len(audios)} audios de {carpeta}")
    return audios


def _clave_visual(v: dict) -> str:
    """Clave de cache por identidad visual (misma foto/gráfica/escena = 1 sola imagen)."""
    t = v.get("tipo", "escena")
    if t == "footage":
        return f"footage::{v.get('query','')}"
    if t == "foto":
        return f"foto::{v.get('query','')}"
    if t == "grafica":
        labels = "|".join(x.get("label", "") for x in v.get("series", []))
        return f"grafica::{v.get('titulo','')}::{labels}"
    return f"escena::{v.get('location','')}"


def _animadas_on() -> bool:
    """Gráficas animadas ON por defecto; GRAFICAS_ANIMADAS=0 vuelve a las estáticas."""
    import os
    return os.environ.get("GRAFICAS_ANIMADAS", "1") != "0"


def _grafica_spec_animada(v: dict) -> dict:
    """Convierte el spec de gráfica del guion (data_chart) al de graficas_animadas."""
    series = v.get("series") or []
    datos, resaltar = [], None
    for i, s in enumerate(series):
        try:
            datos.append((str(s.get("label", "")), float(s.get("valor", 0) or 0)))
        except (TypeError, ValueError):
            datos.append((str(s.get("label", "")), 0.0))
        if s.get("resaltar"):
            resaltar = i   # si hay varias resaltadas, gana la ÚLTIMA (suele ser el remate)
    forma = {"barras": "barras", "torta": "reparto",
             "linea": "linea", "numero": "numero"}.get(v.get("forma", "barras"), "barras")
    # OJO: graficas_animadas pega la unidad a CADA valor → debe ser CORTA o las
    # etiquetas se salen de pantalla. Unidades largas ("% del valor del aparato",
    # "millones de USD") se colapsan: "%" si aplica, si no vacío (el título da contexto).
    u = (v.get("unidad", "") or "").strip()
    unidad = "%" if "%" in u else (u if len(u) <= 3 else "")
    spec = {"forma": forma, "titulo": v.get("titulo", ""),
            "unidad": unidad, "datos": datos, "fuente": v.get("fuente", "")}
    if resaltar is not None:
        spec["resaltar"] = resaltar
    return spec


def _render_grafica_animada(v: dict, dest_mp4: Path) -> str:
    """Renderiza la gráfica ANIMADA (clip) y congela el último frame hasta ~30s
    para que el assembler la corte a la duración del segmento sin re-loopear."""
    import subprocess
    from modules.graficas_animadas import render_grafica
    dest_mp4 = Path(dest_mp4)
    raw = dest_mp4.with_suffix(".raw.mp4")
    render_grafica(_grafica_spec_animada(v), str(raw), vertical=False)
    # tpad clona el último frame (congela) — barato, no re-anima al loopear.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw),
                    "-vf", "tpad=stop_mode=clone:stop_duration=27",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-pix_fmt", "yuv420p", str(dest_mp4)], check=True)
    try:
        raw.unlink()
    except Exception:
        pass
    return str(dest_mp4)


def _generar_fondos(segmentos: list[dict], carpeta: Path) -> list[str]:
    """Un fondo 16:9 por identidad visual única. Rutea cada segmento a:
      - foto real (Wikimedia)  ·  gráfica de datos (PIL)  ·  pixel-art (Imagen).
    Foto/gráfica que fallen caen SIEMPRE al pixel-art (nunca rompe el render)."""
    from modules.background_generator import generar_imagen_essay
    from modules.wikimedia_fetcher import fondo_16x9
    from modules.data_chart import render_chart
    carpeta.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = {}
    rutas = []
    for s in segmentos:
        v = s.get("visual") or {"tipo": "escena", "location": s["location"]}
        key = _clave_visual(v)
        if key not in cache:
            idx = len(cache) + 1
            dest = carpeta / f"bg_{idx:02d}.png"
            tipo = v.get("tipo", "escena")
            ruta = None
            try:
                if tipo == "footage":
                    q = v.get("query", "")
                    canal_of = _canal_oficial_para(q)
                    if canal_of:
                        from modules.topical_footage import descargar_footage_directo
                        log.info(f"  [bg {idx}] FOOTAGE OFICIAL ({canal_of}) ← {q[:50]}")
                        ruta = str(descargar_footage_directo(q, canal_pref=canal_of))
                    else:
                        from modules.topical_footage import descargar_footage_cc
                        log.info(f"  [bg {idx}] FOOTAGE CC ← {q[:60]}")
                        ruta = str(descargar_footage_cc(q))
                elif tipo == "foto":
                    log.info(f"  [bg {idx}] FOTO real ← {v.get('query','')[:60]}")
                    ruta = fondo_16x9(v.get("query", ""), dest)
                elif tipo == "grafica":
                    # NUEVO: gráfica ANIMADA (clip .mp4) por defecto — barras que
                    # crecen con ease-out, cifra que sube. El assembler ya sabe usar
                    # un .mp4 como fondo. Si falla, cae al póster estático de siempre.
                    if _animadas_on():
                        try:
                            dest_mp4 = carpeta / f"bg_{idx:02d}.mp4"
                            log.info(f"  [bg {idx}] GRÁFICA ANIMADA ← {v.get('titulo','')[:50]}")
                            ruta = _render_grafica_animada(v, dest_mp4)
                        except Exception as e:
                            log.warning(f"  [bg {idx}] gráfica animada falló ({e}); póster estático")
                            ruta = None
                    if ruta:
                        cache[key] = ruta
                        rutas.append(cache[key])
                        continue
                    # ── Póster estático (fallback / GRAFICAS_ANIMADAS=0) ──────────
                    # ESTILO PÓSTER SIEMPRE: la gráfica se dibuja sobre un fondo
                    # situacional de Imagen (regla de estilo del canal — los datos
                    # reales van ENCIMA de la escena, nunca en slate plano). Si el
                    # guion no lo marcó, lo forzamos y derivamos el fondo_prompt del
                    # escenario del propio segmento (o del título de la gráfica), para
                    # diversificar los fondos. Ver reference-gato-estilo-graficas.
                    v.setdefault("estilo", "poster")
                    if not v.get("fondo_prompt"):
                        v["fondo_prompt"] = s.get("location") or v.get("titulo", "")
                    log.info(f"  [bg {idx}] GRÁFICA (poster) ← {v.get('titulo','')[:60]}")
                    fp = v.get("fondo_prompt")
                    if fp and v.get("estilo") == "poster" and not v.get("fondo"):
                        try:
                            bg_dest = carpeta / f"chartbg_{idx:02d}.png"
                            v["fondo"] = generar_imagen_essay(fp, bg_dest)
                        except Exception as e:
                            log.warning(f"  [bg {idx}] fondo situacional de gráfica falló ({e}); slate plano")
                    ruta = render_chart(v, dest)
            except Exception as e:
                log.warning(f"  [bg {idx}] {tipo} falló ({e}); caigo a pixel-art")
                ruta = None
            if not ruta:                                   # fallback pixel-art (escena)
                loc = v.get("location") or s["location"]
                log.info(f"  [bg {idx}] pixel-art ← {loc[:60]}")
                ruta = generar_imagen_essay(loc, dest)
            cache[key] = ruta
        rutas.append(cache[key])
    log.info(f"  {len(cache)} fondos únicos para {len(segmentos)} segmentos")
    return rutas


def _fmt_ts(seg: float) -> str:
    m = int(seg // 60); s = int(seg % 60)
    return f"{m}:{s:02d}"


def correr_essay(tema: str, publicar: bool = False, reuse_audio: str = "",
                 reuse_script: str = "", script_only: bool = False) -> dict:
    banner(f"VIDEO-ENSAYO DE ECONOMÍA — {tema}")
    clave = tema.strip().lower()
    outline = OUTLINES.get(clave)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if reuse_audio or reuse_script:
        carpeta_audio = reuse_audio or reuse_script
        banner(f"PASO 1 — Reusando guion de {carpeta_audio}")
        script = json.loads((Path(carpeta_audio) / "script.json").read_text(encoding="utf-8"))
        segmentos = script["segmentos"]
    else:
        # ── 1a. FICHA DE DATOS VERIFICADOS (web search — el alma del formato) ──
        banner("PASO 1a — Fact-check con búsqueda web")
        from modules.fact_checker import generar_ficha_datos
        # max_tokens 3000: con 2000 la ficha del Mundial se TRUNCÓ a media sección
        # (el modelo escribe con encabezados verbosos) y un capítulo quedó sin datos.
        ficha = generar_ficha_datos(tema, max_uses=6, max_vinetas=20, max_tokens=3000,
                                    enfoque=FICHA_ENFOQUE.get(clave, ""))
        if ficha:
            log.info(f"  Ficha verificada:\n{ficha}")
        else:
            log.warning("  ⚠ Sin ficha — el guion NO afirmará cifras (revisar antes de publicar)")

        # ── 1b. GUION ──────────────────────────────────────────────────────
        banner("PASO 1b — Guion del ensayo (Claude, dúo + tarjetas de datos)")
        from modules.essay_script_generator import generar_essay
        script = generar_essay(tema, outline=outline, ficha_datos=ficha)
        segmentos = script["segmentos"]
        carpeta_audio = f"audio/ESSAY_{_slug(script['titulo'])[:30]}_{ts}"
        Path(carpeta_audio).mkdir(parents=True, exist_ok=True)
        Path(carpeta_audio, "script.json").write_text(
            json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        if ficha:
            Path(carpeta_audio, "ficha_datos.txt").write_text(ficha, encoding="utf-8")
        log.info(f"  Guion + ficha guardados en {carpeta_audio}")

    titulo = script["titulo"]

    if script_only:
        banner("GUION LISTO (modo --script-only, no se gastó voz/imágenes)")
        log.info(f"  Título: {titulo}")
        for s in segmentos:
            d = f"  [💳 {s['dato']['cifra']}]" if s.get("dato") else ""
            log.info(f"  {s['numero']:02d} [{s['speaker']:6s}] ({s.get('capitulo','')}) "
                     f"{s['narracion'][:70]}...{d}")
        log.info(f"\n  Revisa {carpeta_audio}/script.json y luego corre:\n"
                 f"  python run_essay.py \"{tema}\" --reuse-script {carpeta_audio}")
        return {"status": "script_only", "carpeta": str(carpeta_audio), "titulo": titulo}

    # ── 2. VOZ (dúo, timestamps exactos) ───────────────────────────────────
    if reuse_audio:
        audios = _cargar_audios_existentes(reuse_audio, segmentos)
    else:
        banner("PASO 2 — Voz (ElevenLabs: Gato + Bastet, timestamps)")
        from modules.essay_voice import generar_audios_essay
        audios = generar_audios_essay(segmentos, carpeta_salida=carpeta_audio)
        # Masterización OPCIONAL (MASTER_VOZ=1): solo sonido, misma duración → no
        # desincroniza los subtítulos por timestamp. Apagado por defecto.
        from modules.voz_hook import masterizar_si_activado
        for _a in audios:
            masterizar_si_activado(_a.get("ruta_audio"))

    # ── 3. FONDOS 16:9 (Imagen, cache por location) ────────────────────────
    banner("PASO 3 — Fondos 16:9 (foto real / gráfica de datos / pixel-art)")
    carpeta_imgs = BASE_DIR / "images" / f"ESSAY_{_slug(titulo)[:30]}_{ts}"
    fondos = _generar_fondos(segmentos, carpeta_imgs)

    # ── 4. MÚSICA por capítulo (Lyria, identidad situacional del guion) ────
    banner("PASO 4 — Música por capítulo (Lyria)")
    mood = script.get("musica_mood", "economia")
    caps = []
    for s in segmentos:
        c = s.get("capitulo", "") or "Capítulo"
        if not caps or caps[-1] != c:
            if c not in caps:
                caps.append(c)
    palette = [mood, "tension", "ambient_misterioso", "dramatico", "lofi"]
    palette = list(dict.fromkeys(palette))
    sin_musica_idx = len(caps) // 2 if len(caps) >= 4 else -1
    musica_por_capitulo = {}
    try:
        from modules.music_generator import generar_musica_lyria
        beds = {}
        for i, c in enumerate(caps):
            if i == sin_musica_idx:
                musica_por_capitulo[c] = None
                log.info(f"  Capítulo '{c}': SIN música (contraste)")
                continue
            mm = palette[i % len(palette)]
            if mm not in beds:
                beds[mm] = generar_musica_lyria(
                    mm, f"{tema} — {mm}", 45,
                    prompt_situacional=script.get("musica_prompt", ""))
                log.info(f"  Bed '{mm}': {beds[mm].name if beds[mm] else 'falló'}")
            musica_por_capitulo[c] = beds.get(mm)
    except Exception as e:
        log.warning(f"  Lyria falló ({e}) — ensayo sin música.")
        musica_por_capitulo = {}

    # ── 5. ENSAMBLE 16:9 ───────────────────────────────────────────────────
    banner("PASO 5 — Ensamble 16:9 (tarjetas de datos + personajes + subtítulos)")
    from modules.essay_assembler import EssayAssembler
    bloques = []
    for a, s, img in zip(audios, segmentos, fondos):
        # Gráfica ANIMADA a pantalla completa: el clip ES el protagonista → sin
        # personaje encima ni tarjeta de dato redundante (la cifra ya va en la gráfica).
        es_chart_video = (_animadas_on()
                          and (s.get("visual") or {}).get("tipo") == "grafica"
                          and str(img).lower().endswith((".mp4", ".mkv", ".webm")))
        bloques.append({"numero": a["numero"], "ruta_audio": a["ruta_audio"],
                        "ruta_imagen": img, "palabras": a.get("palabras", []),
                        "speaker": s.get("speaker", "gato"), "pose": s.get("pose"),
                        "dato": None if es_chart_video else s.get("dato"),
                        "capitulo": s.get("capitulo", ""),
                        "chart_video": es_chart_video,
                        "tiene_visual": (s.get("visual") or {}).get("tipo") in ("foto", "grafica", "footage")})
    output_name = f"{ts}_ESSAY_{_slug(titulo)[:35]}"
    assembler = EssayAssembler()
    ruta_video, capitulos = assembler.ensamblar(bloques, titulo=titulo,
                                                musica_por_capitulo=musica_por_capitulo,
                                                output_name=output_name)

    # ── 5b. DISEÑO DE SONIDO (whoosh en cortes, pop en cifras, ducking) ─────
    # Capa de post-producción sobre el render (la música ya va mezclada, por eso
    # musica=None). Guarded: si falla, deja el video sin SFX y sigue.
    banner("PASO 5b — Diseño de sonido (whoosh/pop/impacto)")
    try:
        from modules.sonido_hook import aplicar_sonido_seguro
        guion_txt = " ".join(s.get("narracion", "") for s in segmentos)
        aplicar_sonido_seguro(ruta_video, guion=guion_txt)
    except Exception as e:
        log.warning(f"  capa de sonido omitida ({e})")

    chap_lines = "\n".join(f"{_fmt_ts(c['t'])} {c['titulo']}" for c in capitulos)
    descripcion = (f"{script.get('descripcion','')}\n\n⏱️ Capítulos:\n{chap_lines}\n\n"
                   + " ".join(h for h in script.get("hashtags", []) if h.lower() != "#shorts"))

    run_log = {"timestamp": datetime.now().isoformat(), "tipo": "ensayo_largo",
               "tema": tema, "titulo": titulo, "ruta_video": str(ruta_video),
               "carpeta_audio": str(carpeta_audio), "capitulos": capitulos,
               "descripcion": descripcion, "status": "success"}
    (LOGS_DIR / f"essay_{ts}.json").write_text(
        json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")

    banner("ENSAYO LISTO")
    log.info(f"  Título: {titulo}")
    log.info(f"  Video:  {ruta_video}")
    log.info(f"  Capítulos:\n{chap_lines}")

    # ── 6. PUBLICAR (solo con --publish; manual) ───────────────────────────
    if publicar:
        banner("PASO 6 — Publicar en YouTube (video normal, NO Short)")
        from publisher import subir_a_youtube, publicar_comentario
        tags = list(dict.fromkeys(
            [t for t in tema.split() if len(t) > 3]
            + [h.lstrip("#") for h in script.get("hashtags", []) if h.lower() != "#shorts"]
        ))[:30]
        metadata = {"titulo": titulo[:100], "descripcion": descripcion,
                    "tags": tags, "tema": tema}
        res = subir_a_youtube(Path(ruta_video), metadata, dry_run=False)
        if res.get("_youtube"):
            publicar_comentario(res["_youtube"], res["video_id"], metadata, {"script": script})
        run_log["url"] = res.get("url", "")
        log.info(f"  ✅ Publicado: {res.get('url','')}")
    else:
        log.info("  (sin --publish) — video en videos_largos/. Revísalo y publica "
                 "con --reuse-audio + --publish, o ad-hoc con publisher.subir_a_youtube.")
    return run_log


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    publicar = "--publish" in args
    if publicar:
        args.remove("--publish")
    script_only = "--script-only" in args
    if script_only:
        args.remove("--script-only")
    reuse_audio = reuse_script = ""
    if "--reuse-audio" in args:
        i = args.index("--reuse-audio")
        reuse_audio = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    if "--reuse-script" in args:
        i = args.index("--reuse-script")
        reuse_script = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    tema = " ".join(args).strip() or "el negocio del mundial"
    correr_essay(tema, publicar=publicar, reuse_audio=reuse_audio,
                 reuse_script=reuse_script, script_only=script_only)
