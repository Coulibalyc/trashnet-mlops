"""Étape 2 : entraîne le modèle, l'exporte en ONNX, le quantize et l'envoie dans MLflow.

Usage :
    python training/train.py                       # entraînement complet
    python training/train.py --epochs-head 2 --epochs-finetune 1   # rapide
Variables :
    MLFLOW_TRACKING_URI   (par défaut http://localhost:5050)
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import mlflow
import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn as nn
import timm
from onnxruntime.quantization import (CalibrationDataReader, QuantFormat,
                                      QuantType, quantize_static)
from onnxruntime.quantization.shape_inference import quant_pre_process
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from app.drift import FEATURES, image_features  # noqa: E402  (même code que l'API)

DATA, RAW = ROOT / "data", ROOT / "data" / "raw"
MODELS, RESULTS = ROOT / "models", ROOT / "results"
CLASSES = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
MODEL_NAME = "trashnet-classifier"
# EfficientNet-Lite0 : version d'EfficientNet conçue pour la quantization int8
# (ReLU6 au lieu de Swish, pas de blocs SE). Poids ImageNet hébergés sur GitHub.
WEIGHTS_URL = ("https://github.com/rwightman/pytorch-image-models/releases/download/"
               "v0.1-weights/efficientnet_lite0_ra-37913777.pth")

train_tf = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.6, 1.0)),
    transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
    transforms.ColorJitter(0.2, 0.2, 0.2),
    transforms.ToTensor(), transforms.Normalize(MEAN, STD)])
eval_tf = transforms.Compose([
    transforms.Resize(224), transforms.CenterCrop(224),
    transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


class TrashDataset(Dataset):
    def __init__(self, files, tf):
        self.files, self.tf = files, tf

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        f = self.files[i]
        return self.tf(Image.open(RAW / f).convert("RGB")), CLASSES.index(f.split("/")[0])


# Accélération : puce Apple (MPS) sur Mac, carte NVIDIA (CUDA) sinon, ou CPU
DEVICE = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


def run_epoch(model, loader, opt=None):
    model.train(opt is not None)
    crit = nn.CrossEntropyLoss()
    total, correct, loss_sum = 0, 0, 0.0
    preds, labels = [], []
    with torch.set_grad_enabled(opt is not None):
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            out = model(x)
            loss = crit(out, y)
            if opt:
                opt.zero_grad()
                loss.backward()
                opt.step()
            loss_sum += loss.item() * len(y)
            p = out.argmax(1)
            correct += (p == y).sum().item()
            total += len(y)
            preds += p.tolist()
            labels += y.tolist()
    return loss_sum / total, correct / total, preds, labels


class Calib(CalibrationDataReader):
    """Donne quelques images au quantizer pour qu'il mesure les valeurs."""
    def __init__(self, files):
        self.it = iter([{"input": eval_tf(Image.open(RAW / f).convert("RGB")).unsqueeze(0).numpy()}
                        for f in files])

    def get_next(self):
        return next(self.it, None)


def eval_onnx(path, files):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    preds, labels, times = [], [], []
    for f in files:
        x = eval_tf(Image.open(RAW / f).convert("RGB")).unsqueeze(0).numpy()
        t = time.perf_counter()
        out = sess.run(None, {"input": x})[0]
        times.append((time.perf_counter() - t) * 1000)
        preds.append(int(out.argmax()))
        labels.append(CLASSES.index(f.split("/")[0]))
    return {"accuracy": accuracy_score(labels, preds),
            "f1_macro": f1_score(labels, preds, average="macro"),
            "latency_ms": float(np.median(times)),
            "size_mb": path.stat().st_size / 1e6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs-head", type=int, default=5)
    ap.add_argument("--epochs-finetune", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--promote", action="store_true",
                    help="met l'alias 'champion' sur ce modèle = mise en production")
    args = ap.parse_args()

    torch.manual_seed(0)
    random.seed(0)
    MODELS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    splits = json.loads((DATA / "splits.json").read_text())
    dl = lambda k, tf, sh: DataLoader(TrashDataset(splits[k], tf), args.batch_size,
                                      shuffle=sh, num_workers=2)
    train_dl, val_dl, test_dl = dl("train", train_tf, True), dl("val", eval_tf, False), dl("test", eval_tf, False)

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050"))
    mlflow.set_experiment("trashnet")
    with mlflow.start_run() as run:
        mlflow.log_params(vars(args) | {"model": "efficientnet-lite0", "img_size": 224,
                                        "n_train": len(splits["train"])})

        model = timm.create_model("efficientnet_lite0", pretrained=False)
        model.load_state_dict(torch.hub.load_state_dict_from_url(WEIGHTS_URL, map_location="cpu"))
        model.reset_classifier(len(CLASSES))
        model.to(DEVICE)
        print(f"Entraînement sur : {DEVICE}")
        history = []

        # Phase 1 : on gèle le modèle pré-entraîné, on n'apprend que la dernière couche
        for p in model.parameters():
            p.requires_grad = False
        for p in model.classifier.parameters():
            p.requires_grad = True
        opt = torch.optim.AdamW(model.classifier.parameters(), lr=1e-3)
        # Phase 2 : on dégèle les derniers blocs, avec un learning rate plus petit
        n_total = args.epochs_head + args.epochs_finetune
        for epoch in range(n_total):
            if epoch == args.epochs_head:
                for m in [*model.blocks[-3:], model.conv_head, model.bn2]:
                    for p in m.parameters():
                        p.requires_grad = True
                opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4)
            t = time.time()
            tl, ta, _, _ = run_epoch(model, train_dl, opt)
            vl, va, _, _ = run_epoch(model, val_dl)
            history.append({"epoch": epoch + 1, "train_loss": tl, "train_acc": ta,
                            "val_loss": vl, "val_acc": va})
            mlflow.log_metrics({"train_loss": tl, "train_acc": ta, "val_loss": vl, "val_acc": va}, step=epoch + 1)
            print(f"epoch {epoch+1}/{n_total} train_acc={ta:.3f} val_acc={va:.3f} ({time.time()-t:.0f}s)")

        # Évaluation finale sur le jeu de test (jamais vu)
        _, test_acc, preds, labels = run_epoch(model, test_dl)
        f1s = f1_score(labels, preds, average=None)
        cm = confusion_matrix(labels, preds)
        mlflow.log_metrics({"test_acc": test_acc, "test_f1_macro": float(np.mean(f1s))})

        # Export ONNX (format standard, lu sans PyTorch dans l'API)
        model.to("cpu").eval()
        fp32 = MODELS / "model_fp32.onnx"
        torch.onnx.export(model, torch.randn(1, 3, 224, 224), str(fp32), input_names=["input"],
                          output_names=["logits"], dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
                          opset_version=17, dynamo=False)

        # Quantization int8 : poids en 8 bits au lieu de 32 -> modèle ~4x plus petit
        pre = MODELS / "model_pre.onnx"
        quant_pre_process(str(fp32), str(pre))
        int8 = MODELS / "model_int8.onnx"
        quantize_static(str(pre), str(int8), Calib(splits["train"][::12]),
                        quant_format=QuantFormat.QDQ, per_channel=True,
                        activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8)
        pre.unlink()

        # Statistiques de référence pour la détection de drift
        ref = {k: [] for k in FEATURES}
        for f in splits["val"]:
            for k, v in image_features(Image.open(RAW / f).convert("RGB")).items():
                ref[k].append(round(v, 4))

        # On range labels + stats de référence DANS le fichier ONNX (un seul fichier à déployer)
        for path in (fp32, int8):
            m = onnx.load(str(path))
            for key, val in {"labels": json.dumps(CLASSES), "reference_stats": json.dumps(ref),
                             "mlflow_run_id": run.info.run_id}.items():
                p = m.metadata_props.add()
                p.key, p.value = key, val
            onnx.save(m, str(path))

        bench = {"fp32": eval_onnx(fp32, splits["test"]), "int8": eval_onnx(int8, splits["test"])}
        for k, v in bench.items():
            mlflow.log_metrics({f"{k}_{m}": x for m, x in v.items()})
        print(json.dumps(bench, indent=1))

        summary = {"test_acc": test_acc, "f1_per_class": dict(zip(CLASSES, map(float, f1s))),
                   "confusion_matrix": cm.tolist(), "classes": CLASSES, "history": history, "epochs_head": args.epochs_head,
                   "bench": bench, "splits": {k: len(v) for k, v in splits.items()},
                   "run_id": run.info.run_id}
        (RESULTS / "training_summary.json").write_text(json.dumps(summary, indent=1))
        mlflow.log_artifact(str(RESULTS / "training_summary.json"))

        # Enregistrement dans le Model Registry de MLflow (versionnage)
        info = mlflow.onnx.log_model(onnx.load(str(int8)), name="model",
                                     registered_model_name=MODEL_NAME)
        version = info.registered_model_version
        print(f"Modèle enregistré : {MODEL_NAME} version {version}")
        if args.promote:
            mlflow.MlflowClient().set_registered_model_alias(MODEL_NAME, "champion", version)
            print("Alias 'champion' posé -> redémarrer l'API pour charger cette version")


if __name__ == "__main__":
    main()
