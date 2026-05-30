"""Seed cost_tracker.json from existing run logs (one-time migration)."""
import json
from pathlib import Path

logs_dir = Path(__file__).parent.parent / "logs"
tracker = {
    "runs": [],
    "totals": {
        "anthropic_usd": 0.0,
        "elevenlabs_usd": 0.0,
        "openai_usd": 0.0,
        "falai_usd": 0.0,
        "grand_total": 0.0,
        "videos_completados": 0,
    },
}

for f in sorted(logs_dir.glob("run_*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not d.get("status", "").startswith("success"):
        continue
    c = d.get("costos", {})
    ant = c.get("script_usd", 0) or 0
    el  = c.get("audio_usd", 0) or 0
    oa  = c.get("imagenes_usd", 0) or 0
    fa  = c.get("animacion_usd", 0) or 0
    tot = c.get("total_usd", 0) or 0
    if tot == 0:
        tot = round(ant + el + oa + fa, 4)
    if tot == 0:
        continue
    entry = {
        "timestamp":      d.get("timestamp", ""),
        "tema":           d.get("tema", ""),
        "anthropic_usd":  ant,
        "elevenlabs_usd": el,
        "openai_usd":     oa,
        "falai_usd":      fa,
        "total_usd":      tot,
    }
    tracker["runs"].append(entry)
    tracker["totals"]["anthropic_usd"]      += ant
    tracker["totals"]["elevenlabs_usd"]     += el
    tracker["totals"]["openai_usd"]         += oa
    tracker["totals"]["falai_usd"]          += fa
    tracker["totals"]["grand_total"]        += tot
    tracker["totals"]["videos_completados"] += 1

for k in ("anthropic_usd", "elevenlabs_usd", "openai_usd", "falai_usd", "grand_total"):
    tracker["totals"][k] = round(tracker["totals"][k], 4)

out = logs_dir / "cost_tracker.json"
out.write_text(json.dumps(tracker, ensure_ascii=False, indent=2), encoding="utf-8")

t = tracker["totals"]
print(f"Seeded {t['videos_completados']} runs into {out.name}")
print(f"  Claude total:     ${t['anthropic_usd']:.3f}")
print(f"  ElevenLabs total: ${t['elevenlabs_usd']:.3f}")
print(f"  OpenAI total:     ${t['openai_usd']:.3f}  -> saldo restante ~${5.00 - t['openai_usd']:.2f}")
print(f"  fal.ai total:     ${t['falai_usd']:.3f}  -> saldo restante ~${10.00 - t['falai_usd']:.2f}")
print(f"  GRAND TOTAL:      ${t['grand_total']:.3f}")
