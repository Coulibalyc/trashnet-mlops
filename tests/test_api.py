"""Tests automatiques de l'API (lancés par la pipeline CD avant chaque déploiement)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(DATABASE_URL="sqlite:///:memory:", ADMIN_TOKEN="test-admin",
                  MODEL_PATH=str(ROOT / "models" / "model_int8.onnx"))
os.environ.pop("MLFLOW_MODEL_URI", None)
sys.path.insert(0, str(ROOT / "api"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db as db  # noqa: E402

db.engine = db.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
db.Session.configure(bind=db.engine)
from app.main import app  # noqa: E402

client = TestClient(app)
IMG = next((ROOT / "loadtest" / "images").glob("*.jpg")).read_bytes()


def make_user(name):
    r = client.post("/admin/users", json={"name": name}, headers={"X-Admin-Key": "test-admin"})
    assert r.status_code == 200
    return r.json()["token"]


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_predict_requires_token():
    assert client.post("/predict", files={"file": ("a.jpg", IMG)}).status_code == 401
    assert client.post("/predict", files={"file": ("a.jpg", IMG)},
                       headers={"X-API-Key": "faux"}).status_code == 401


def test_admin_requires_key():
    assert client.get("/admin/usage", headers={"X-Admin-Key": "faux"}).status_code == 401


def test_predict_and_usage():
    token = make_user("alice")
    r = client.post("/predict", files={"file": ("a.jpg", IMG)}, headers={"X-API-Key": token})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] in body["probabilities"]
    assert abs(sum(body["probabilities"].values()) - 1) < 0.01
    usage = client.get("/me/usage", headers={"X-API-Key": token}).json()
    assert usage[0]["user"] == "alice" and usage[0]["requests"] == 1


def test_bad_image():
    token = make_user("bob")
    r = client.post("/predict", files={"file": ("a.jpg", b"pas une image")}, headers={"X-API-Key": token})
    assert r.status_code == 400
