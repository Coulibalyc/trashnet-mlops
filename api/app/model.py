"""Chargement du modèle ONNX (depuis MLflow ou un fichier local) et prédiction."""
import json
import logging
import os
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from PIL import Image

log = logging.getLogger("model")
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class Classifier:
    def __init__(self):
        path, self.version = self._locate()
        meta = {p.key: p.value for p in onnx.load(str(path)).metadata_props}
        self.labels = json.loads(meta["labels"])
        self.reference = json.loads(meta["reference_stats"])
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.getenv("ORT_THREADS", "1"))
        self.session = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
        log.info("Modèle chargé : %s (version %s)", path, self.version)

    @staticmethod
    def _locate():
        """1) MLflow Model Registry si configuré  2) sinon fichier local."""
        uri = os.getenv("MLFLOW_MODEL_URI")      # ex : models:/trashnet-classifier@champion
        if uri:
            try:
                import mlflow
                from mlflow import MlflowClient
                local = Path(mlflow.artifacts.download_artifacts(uri))
                name, alias = uri.removeprefix("models:/").split("@")
                version = MlflowClient().get_model_version_by_alias(name, alias).version
                return next(local.rglob("*.onnx")), f"mlflow-v{version}"
            except Exception as e:  # MLflow vide ou injoignable -> on ne plante pas
                log.warning("MLflow indisponible (%s), on utilise le modèle local", e)
        return Path(os.getenv("MODEL_PATH", "/models/model_int8.onnx")), "local"

    @staticmethod
    def preprocess(img: Image.Image) -> np.ndarray:
        img = img.convert("RGB")
        w, h = img.size
        s = 224 / min(w, h)
        img = img.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BILINEAR)
        w, h = img.size
        left, top = (w - 224) // 2, (h - 224) // 2
        a = np.asarray(img.crop((left, top, left + 224, top + 224)), dtype=np.float32) / 255.0
        return ((a - MEAN) / STD).transpose(2, 0, 1)[None]

    def predict(self, img: Image.Image) -> dict:
        logits = self.session.run(None, {"input": self.preprocess(img)})[0][0]
        e = np.exp(logits - logits.max())
        probs = e / e.sum()
        i = int(probs.argmax())
        return {"label": self.labels[i], "confidence": round(float(probs[i]), 4),
                "probabilities": {l: round(float(p), 4) for l, p in zip(self.labels, probs)}}
