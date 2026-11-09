"""API de classification des déchets.

Toutes les routes (sauf /health) demandent un token dans le header :
    X-API-Key: <token utilisateur>        (routes /predict, /me/...)
    X-Admin-Key: <token admin>            (routes /admin/...)
"""
import io
import logging
import os
import secrets
import socket
import time

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import select

from .db import Prediction, Session, User, find_user, hash_token, init_db, usage_by_user
from .drift import FEATURES, compute_drift, image_features
from .model import Classifier

logging.basicConfig(level=logging.INFO)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me")
INSTANCE = socket.gethostname()      # identifiant du conteneur, utile pour voir le load balancing
MAX_BYTES = 5 * 1024 * 1024

app = FastAPI(title="TrashNet API", version="1.0", root_path=os.getenv("ROOT_PATH", ""))
init_db()
model = Classifier()


@app.middleware("http")
async def add_instance_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Instance"] = INSTANCE
    return response


# ---------- Sécurité ----------
def current_user(x_api_key: str = Header(None)) -> str:
    user = find_user(x_api_key) if x_api_key else None
    if not user:
        raise HTTPException(401, "Token manquant ou invalide (header X-API-Key)")
    return user.name


def admin(x_admin_key: str = Header(None)):
    if not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_TOKEN):
        raise HTTPException(401, "Clé admin invalide (header X-Admin-Key)")


# ---------- Routes publiques ----------
@app.get("/health")
def health():
    return {"status": "ok", "instance": INSTANCE, "model_version": model.version}


# ---------- Routes utilisateur ----------
@app.post("/predict")
def predict(file: UploadFile = File(...), user: str = Depends(current_user)):
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image trop grande (max 5 Mo)")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Fichier image invalide")

    t = time.perf_counter()
    result = model.predict(img)
    latency = (time.perf_counter() - t) * 1000

    with Session() as s:          # suivi de l'usage par utilisateur + données pour le drift
        s.add(Prediction(user=user, label=result["label"], confidence=result["confidence"],
                         latency_ms=latency, instance=INSTANCE, model_version=model.version,
                         **image_features(img)))
        s.commit()
    return result | {"latency_ms": round(latency, 1), "model_version": model.version,
                     "instance": INSTANCE}


@app.get("/me/usage")
def my_usage(user: str = Depends(current_user)):
    return usage_by_user(user)


# ---------- Routes admin ----------
class NewUser(BaseModel):
    name: str


@app.post("/admin/users", dependencies=[Depends(admin)])
def create_user(body: NewUser):
    token = secrets.token_urlsafe(24)
    with Session() as s:
        if s.scalar(select(User).where(User.name == body.name)):
            raise HTTPException(409, "Utilisateur déjà existant")
        s.add(User(name=body.name, token_hash=hash_token(token)))
        s.commit()
    return {"name": body.name, "token": token, "info": "Gardez ce token, il ne sera plus affiché"}


@app.get("/admin/usage", dependencies=[Depends(admin)])
def all_usage():
    return usage_by_user()


@app.get("/admin/drift", dependencies=[Depends(admin)])
def drift(window: int = 200):
    with Session() as s:
        rows = s.scalars(select(Prediction).order_by(Prediction.id.desc()).limit(window)).all()
        current = [{f: getattr(r, f) for f in FEATURES} for r in rows]
        labels = {}
        for r in rows:
            labels[r.label] = labels.get(r.label, 0) + 1
    return compute_drift(model.reference, current) | {"label_distribution": labels}
