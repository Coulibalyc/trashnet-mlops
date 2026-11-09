"""Vérifie que la sécurité de l'API fonctionne (codes HTTP attendus).

    python scripts/check_security.py --url http://<IP>/api --token <TOKEN> --admin <ADMIN_TOKEN>
"""
import argparse
import json
from pathlib import Path

import requests

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost/api")
ap.add_argument("--token", required=True)
ap.add_argument("--admin", required=True)
a = ap.parse_args()

img = next((Path(__file__).resolve().parents[1] / "loadtest" / "images").glob("*.jpg")).read_bytes()
f = lambda data=img: {"file": ("x.jpg", data)}
cases = [
    ("Prédiction sans token", lambda: requests.post(f"{a.url}/predict", files=f()), 401),
    ("Prédiction avec un faux token", lambda: requests.post(f"{a.url}/predict", files=f(), headers={"X-API-Key": "faux"}), 401),
    ("Prédiction avec un bon token", lambda: requests.post(f"{a.url}/predict", files=f(), headers={"X-API-Key": a.token}), 200),
    ("Fichier qui n'est pas une image", lambda: requests.post(f"{a.url}/predict", files=f(b"abc"), headers={"X-API-Key": a.token}), 400),
    ("Image de plus de 5 Mo", lambda: requests.post(f"{a.url}/predict", files=f(b"0" * 6_000_000), headers={"X-API-Key": a.token}), 413),
    ("Route admin avec un token utilisateur", lambda: requests.get(f"{a.url}/admin/usage", headers={"X-Admin-Key": a.token}), 401),
    ("Route admin avec la clé admin", lambda: requests.get(f"{a.url}/admin/usage", headers={"X-Admin-Key": a.admin}), 200),
]
results = []
for name, call, expected in cases:
    code = call().status_code
    results.append({"case": name, "expected": expected, "got": code, "ok": code == expected})
    print(f"{'✅' if code == expected else '❌'} {name:40s} attendu {expected}  obtenu {code}")
Path("results").mkdir(exist_ok=True)
Path("results/security_checks.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
