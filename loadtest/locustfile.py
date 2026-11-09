"""Test de charge avec Locust.

    export LOCUST_TOKEN=<token utilisateur>
    locust -f loadtest/locustfile.py --host http://<IP>/api \
           --headless -u 50 -r 5 -t 3m --csv results/locust
"""
import os
import random
from pathlib import Path

from locust import HttpUser, between, task

IMAGES = [p.read_bytes() for p in (Path(__file__).parent / "images").glob("*.jpg")]
TOKEN = os.environ["LOCUST_TOKEN"]


class TrashUser(HttpUser):
    wait_time = between(0.5, 1.5)        # chaque utilisateur virtuel attend 0.5 à 1.5 s

    @task(10)
    def predict(self):
        self.client.post("/predict", headers={"X-API-Key": TOKEN},
                         files={"file": ("img.jpg", random.choice(IMAGES))})

    @task(1)
    def health(self):
        self.client.get("/health")

    @task(1)
    def no_token(self):                   # vérifie que la sécurité tient sous la charge
        with self.client.post("/predict", files={"file": ("img.jpg", IMAGES[0])},
                              catch_response=True, name="/predict (sans token)") as r:
            if r.status_code == 401:
                r.success()
