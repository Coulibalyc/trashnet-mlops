"""Base de données : les utilisateurs (tokens) et l'historique des requêtes."""
import hashlib
import os
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, Integer, String, create_engine,
                        func, select)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trashnet.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    token_hash = Column(String, unique=True, nullable=False)   # on ne stocke jamais le token en clair
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    user = Column(String, index=True)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    label = Column(String)
    confidence = Column(Float)
    latency_ms = Column(Float)
    instance = Column(String)          # quel conteneur API a répondu (scaling)
    model_version = Column(String)
    brightness = Column(Float)
    contrast = Column(Float)
    red = Column(Float)
    green = Column(Float)
    blue = Column(Float)
    saturation = Column(Float)


def init_db():
    Base.metadata.create_all(engine)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def find_user(token: str):
    with Session() as s:
        return s.scalar(select(User).where(User.token_hash == hash_token(token)))


def usage_by_user(user: str | None = None):
    with Session() as s:
        q = select(Prediction.user, func.count(), func.avg(Prediction.latency_ms),
                   func.max(Prediction.ts)).group_by(Prediction.user)
        if user:
            q = q.where(Prediction.user == user)
        return [{"user": u, "requests": n, "avg_latency_ms": round(lat or 0, 1),
                 "last_request": str(last)} for u, n, lat, last in s.execute(q)]
