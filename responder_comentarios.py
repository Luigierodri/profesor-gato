#!/usr/bin/env python
"""
Responder de comentarios — canal Profesor Gato.

Flujo en DOS pasos (nunca publica a ciegas):

  1) python responder_comentarios.py            # = --scan
     Escanea los uploads recientes, detecta comentarios de espectadores SIN
     respuesta del canal, redacta una réplica con Claude en la voz del canal y
     las guarda en data/comentarios_pendientes.json para que las revises.

  2) python responder_comentarios.py --publish
     Lee ese JSON y publica cada réplica (parentId = id del comentario top-level).
     Marca cada una como "posteada" y guarda el id de la respuesta.

Opcionales:
  --videos N    cuántos uploads recientes escanear (default 30)
  --solo-faltantes   en --scan, no re-redacta las que ya tienen borrador
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from googleapiclient.discovery import build

from publisher import obtener_credenciales
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

BASE_DIR = Path(__file__).resolve().parent
PENDIENTES = BASE_DIR / "data" / "comentarios_pendientes.json"

VOZ = """Eres el community manager del canal de YouTube "Profesor Gato", un canal
educativo en español (México) sobre finanzas, economía e historia narrada.
El personaje es el Profesor Gato (un gato que explica) junto a Bastet.

Escribe UNA respuesta a un comentario de un espectador. Reglas de voz:
- Tono cercano, inteligente y casual de YouTuber, español de México.
- CORTA: 1-2 frases, máximo ~220 caracteres.
- 1 o 2 emojis como mucho; usa 🐱 o 🐾 cuando encaje (no obligatorio).
- Aporta algo (un mini-dato, un matiz o una pregunta) o agradece con calidez.
- Invita sutilmente a seguir viendo/suscribirse SOLO si fluye natural.
- NUNCA tomes partido político ni de un partido; si el comentario es político,
  responde con un principio neutral y educativo, sin señalar a un bando.
- Si el comentario es un insulto o corrección, responde con humildad y elegancia,
  sin escalar. Nada de sarcasmo agresivo.
- No inventes datos. No uses comillas alrededor de tu respuesta.
Devuelve SOLO el texto de la respuesta, sin nada más."""


def _yt():
    creds = obtener_credenciales()
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _cargar():
    if PENDIENTES.exists():
        return json.loads(PENDIENTES.read_text(encoding="utf-8"))
    return []


def _guardar(data):
    PENDIENTES.parent.mkdir(parents=True, exist_ok=True)
    PENDIENTES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def redactar(client, titulo, comentario):
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        system=VOZ,
        messages=[{
            "role": "user",
            "content": (
                f"Video: «{titulo}»\n"
                f"Comentario del espectador: «{comentario}»\n\n"
                f"Tu respuesta:"
            ),
        }],
    )
    return msg.content[0].text.strip().strip('"').strip()


def escanear(n_videos, solo_faltantes):
    yt = _yt()
    me = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = me["contentDetails"]["relatedPlaylists"]["uploads"]
    my_id = me["id"]

    ids, page = [], None
    while len(ids) < n_videos:
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                     maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in pl["items"]]
        page = pl.get("nextPageToken")
        if not page:
            break
    ids = ids[:n_videos]

    titulos = {}
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()["items"]:
            titulos[v["id"]] = v["snippet"]["title"]

    existentes = _cargar()
    ya = {p["comment_id"] for p in existentes}
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    nuevos = 0
    for vid in ids:
        try:
            ct = yt.commentThreads().list(part="snippet,replies", videoId=vid,
                                          maxResults=100, order="time",
                                          textFormat="plainText").execute()
        except Exception:
            continue
        for it in ct.get("items", []):
            top = it["snippet"]["topLevelComment"]
            snip = top["snippet"]
            if snip.get("authorChannelId", {}).get("value") == my_id:
                continue
            replies = it.get("replies", {}).get("comments", [])
            if any(r["snippet"].get("authorChannelId", {}).get("value") == my_id for r in replies):
                continue
            cid = top["id"]
            if cid in ya:
                if solo_faltantes:
                    continue
            texto = snip["textDisplay"]
            titulo = titulos.get(vid, vid)
            print(f"… redactando para @{snip['authorDisplayName']}: {texto[:60]}")
            try:
                respuesta = redactar(client, titulo, texto)
            except Exception as e:
                print(f"   (error Claude: {e})")
                continue
            existentes = [p for p in existentes if p["comment_id"] != cid]
            existentes.append({
                "comment_id": cid,
                "video_id": vid,
                "video_titulo": titulo,
                "autor": snip["authorDisplayName"],
                "comentario": texto,
                "respuesta": respuesta,
                "estado": "borrador",
                "redactado": datetime.now(timezone.utc).isoformat(),
            })
            ya.add(cid)
            nuevos += 1

    _guardar(existentes)
    print(f"\n>>> {nuevos} borradores nuevos. Total pendientes: "
          f"{sum(1 for p in existentes if p['estado'] == 'borrador')}")
    print(f">>> Revisa/edita el archivo: {PENDIENTES}")
    print(">>> Luego: python responder_comentarios.py --publish")


def publicar():
    data = _cargar()
    pend = [p for p in data if p["estado"] == "borrador"]
    if not pend:
        print("No hay borradores pendientes.")
        return
    yt = _yt()
    ok = 0
    for p in data:
        if p["estado"] != "borrador":
            continue
        try:
            r = yt.comments().insert(part="snippet", body={
                "snippet": {"parentId": p["comment_id"], "textOriginal": p["respuesta"]}
            }).execute()
            p["estado"] = "posteada"
            p["reply_id"] = r["id"]
            p["posteado"] = datetime.now(timezone.utc).isoformat()
            ok += 1
            print(f"✓ @{p['autor']}: {p['respuesta'][:60]}")
        except Exception as e:
            print(f"✗ @{p['autor']}: {e}")
    _guardar(data)
    print(f"\nPosteadas {ok}/{len(pend)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="escanear y redactar (default)")
    ap.add_argument("--publish", action="store_true", help="publicar los borradores")
    ap.add_argument("--videos", type=int, default=30, help="uploads recientes a escanear")
    ap.add_argument("--solo-faltantes", action="store_true",
                    help="no re-redactar comentarios que ya tienen borrador")
    args = ap.parse_args()

    if args.publish:
        publicar()
    else:
        escanear(args.videos, args.solo_faltantes)


if __name__ == "__main__":
    main()
