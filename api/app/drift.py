"""Détection de data drift.

Idée simple : pour chaque image reçue on calcule quelques chiffres
(luminosité, contraste, couleurs). On compare ces chiffres récents à ceux
des images d'entraînement avec un test statistique (Kolmogorov-Smirnov).
Si les distributions sont trop différentes -> drift.
"""
import numpy as np
from PIL import Image
from scipy.stats import ks_2samp

FEATURES = ["brightness", "contrast", "red", "green", "blue", "saturation"]
P_VALUE = 0.05          # seuil du test : en dessous, la feature a "drifté"
DRIFT_SHARE = 0.5       # drift global si au moins 50 % des features ont drifté


def image_features(img: Image.Image) -> dict:
    a = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.float32) / 255.0
    gray = a.mean(axis=2)
    hsv = np.asarray(img.convert("RGB").resize((64, 64)).convert("HSV"), dtype=np.float32) / 255.0
    return {"brightness": float(gray.mean()), "contrast": float(gray.std()),
            "red": float(a[..., 0].mean()), "green": float(a[..., 1].mean()),
            "blue": float(a[..., 2].mean()), "saturation": float(hsv[..., 1].mean())}


def compute_drift(reference: dict, current: list[dict]) -> dict:
    if len(current) < 30:
        return {"status": "pas assez de données", "n_current": len(current)}
    details = {}
    for f in FEATURES:
        cur = [row[f] for row in current]
        stat, p = ks_2samp(reference[f], cur)
        details[f] = {"p_value": round(float(p), 4), "drift": bool(p < P_VALUE),
                      "ref_mean": round(float(np.mean(reference[f])), 3),
                      "cur_mean": round(float(np.mean(cur)), 3)}
    share = sum(d["drift"] for d in details.values()) / len(FEATURES)
    return {"status": "DRIFT" if share >= DRIFT_SHARE else "OK", "drift_share": share,
            "n_current": len(current), "features": details}
