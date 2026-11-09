"""Étape 1 : télécharge TrashNet et le découpe en train / val / test.

Usage : python training/prepare_data.py
Résultat : data/raw/<classe>/*.jpg  +  data/splits.json
"""
import json
import random
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = DATA / "trashnet_src"
RAW = DATA / "raw"
CLASSES = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]
SEED = 42


def download():
    if not (SRC / "data" / "dataset-resized.zip").exists():
        print("Téléchargement de TrashNet depuis GitHub...")
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/garythung/trashnet", str(SRC)], check=True)


def extract():
    if RAW.exists():
        return
    print("Décompression...")
    with zipfile.ZipFile(SRC / "data" / "dataset-resized.zip") as z:
        for name in z.namelist():
            parts = Path(name).parts
            if len(parts) == 3 and parts[0] == "dataset-resized" and name.endswith(".jpg"):
                out = RAW / parts[1] / parts[2]
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def split():
    rng = random.Random(SEED)
    splits = {"train": [], "val": [], "test": []}
    for label in CLASSES:
        files = sorted(str(p.relative_to(RAW)) for p in (RAW / label).glob("*.jpg"))
        rng.shuffle(files)
        n = len(files)
        n_val, n_test = int(n * 0.15), int(n * 0.15)
        splits["test"] += files[:n_test]
        splits["val"] += files[n_test:n_test + n_val]
        splits["train"] += files[n_test + n_val:]
        print(f"{label:10s} {n} images")
    (DATA / "splits.json").write_text(json.dumps(splits, indent=1))
    print({k: len(v) for k, v in splits.items()})


if __name__ == "__main__":
    download()
    extract()
    split()
