"""Démo du data drift : on envoie des images normales, puis des images très sombres
(comme si la caméra de l'usine de tri était mal éclairée) et on regarde /admin/drift.

    python scripts/simulate_drift.py --url http://<IP>/api --token <token> --admin <admin>
"""
import argparse
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageEnhance

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost/api")
ap.add_argument("--token", required=True)
ap.add_argument("--admin", required=True)
ap.add_argument("--n", type=int, default=60)
args = ap.parse_args()

images = sorted((Path(__file__).resolve().parents[1] / "loadtest" / "images").glob("*.jpg"))


def send(darken: bool):
    for i in range(args.n):
        img = Image.open(images[i % len(images)]).convert("RGB")
        if darken:
            img = ImageEnhance.Brightness(img).enhance(0.35)
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        requests.post(f"{args.url}/predict", headers={"X-API-Key": args.token},
                      files={"file": ("x.jpg", buf.getvalue())}, timeout=30).raise_for_status()
    d = requests.get(f"{args.url}/admin/drift", params={"window": args.n},
                     headers={"X-Admin-Key": args.admin}, timeout=30).json()
    print(json.dumps({"status": d["status"], "drift_share": d.get("drift_share"),
                      "p_values": {k: v["p_value"] for k, v in d.get("features", {}).items()}}, indent=1))
    return d


print("1) Images normales")
normal = send(False)
print("2) Images sombres")
dark = send(True)
Path("results").mkdir(exist_ok=True)
Path("results/drift_demo.json").write_text(json.dumps({"normal": normal, "dark": dark}, indent=1))
