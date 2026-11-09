# ♻️ TrashNet MLOps — tri automatique des déchets

Une photo de déchet → le modèle dit : **carton, verre, métal, papier, plastique ou ordures**.
Le modèle est servi en production sur AWS, avec sécurité, suivi, drift, MLflow et scaling.

---

## 1. Architecture en une image

```
                    ┌──────────── VM AWS EC2 (créée par Terraform) ────────────┐
 Utilisateur ──►    │  Nginx :80 ──► UI Streamlit                              │
 (navigateur/API)   │     │                                                   │
                    │     └─/api─► API #1 ┐                                   │
                    │              API #2 ├─► Postgres (users, usage, drift)  │
                    │              API #3 ┘                                   │
                    │                 ▲  charge le modèle "champion"           │
                    │              MLflow :5050 (versions du modèle)           │
                    └──────────────────────────────────────────────────────────┘
 GitHub push ──► GitHub Actions (tests ► déploiement)
```

| Dossier | Rôle |
|---|---|
| `training/` | Préparer les données, entraîner, quantizer, envoyer dans MLflow |
| `api/` | Web service FastAPI (token, suivi d'usage, drift) |
| `ui/` | Interface web Streamlit |
| `nginx/` | Porte d'entrée + load balancer |
| `infra/` | Terraform : création de la VM AWS |
| `.github/workflows/` | Pipeline CD |
| `loadtest/` | Test de charge Locust |
| `scripts/` | Déploiement, démo du drift |
| `tests/` | Tests automatiques de l'API |

---

## 2. Installer les outils (Mac Apple Silicon)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
→ installe Homebrew, le gestionnaire de logiciels du Mac (à faire une seule fois).

```bash
brew install python@3.12 git terraform awscli
```
→ installe Python, Git, Terraform et l'outil en ligne de commande AWS.

```bash
brew install --cask docker
```
→ installe Docker Desktop. Ouvre-le une fois (icône baleine dans la barre du haut) pour le démarrer.

```bash
docker --version && terraform -version && aws --version
```
→ vérifie que tout est bien installé.

> L'entraînement utilise automatiquement la puce graphique du Mac (MPS) : bien plus rapide qu'un CPU.
> MLflow est sur le port **5050**, car le port 5000 est pris par AirPlay sur Mac.

---

## 3. Entraîner le modèle (une seule fois)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
```
→ crée un environnement Python isolé et l'active.

```bash
pip install -r training/requirements.txt
```
→ installe PyTorch, MLflow, ONNX…

```bash
python training/prepare_data.py
```
→ télécharge TrashNet (≈2 500 photos) et le coupe en train 70 % / val 15 % / test 15 %.

```bash
docker compose up -d mlflow
```
→ démarre seulement MLflow (pour enregistrer l'entraînement). Interface : http://localhost:5050

```bash
python training/train.py --promote
```
→ entraîne EfficientNet-Lite0 (≈20 min sur CPU), exporte en ONNX, crée la version **int8 quantizée**,
l'enregistre dans MLflow et lui donne l'alias **champion** (= version en production).
Résultats dans `models/` et `results/training_summary.json`.

**Comment ça marche (simple) :**
- *Transfer learning* : on part d'un modèle qui sait déjà voir des images, on lui apprend juste nos 6 classes.
- *EfficientNet-Lite0* : version d'EfficientNet faite pour être compressée en int8 (on a d'abord testé EfficientNet-B0 : bonne précision mais il perdait 24 points une fois compressé).
- *ONNX* : format standard → l'API n'a pas besoin de PyTorch (image Docker 5× plus légère).
- *Quantization int8* : les nombres du modèle passent de 32 à 8 bits → 4× plus petit, plus rapide.

---

## 4. Niveau 0 — tout lancer en local avec UNE commande

```bash
cp .env.example .env
```
→ crée le fichier de secrets (change `ADMIN_TOKEN`).

```bash
docker compose up -d --build
```
→ construit et lance les 7 conteneurs : postgres, mlflow, 3× api, ui, nginx.

```bash
docker compose ps
```
→ affiche les conteneurs et leur état.

Ouvre :
- Interface : http://localhost
- Doc de l'API : http://localhost/api/docs
- MLflow : http://localhost:5050

---

## 5. Niveau 1 — sécurité par token + suivi par utilisateur

```bash
curl -X POST http://localhost/api/admin/users \
  -H "X-Admin-Key: <ADMIN_TOKEN>" -H "Content-Type: application/json" -d '{"name":"yoann"}'
```
→ crée un utilisateur et renvoie **son token** (affiché une seule fois, stocké haché en base).

```bash
curl -X POST http://localhost/api/predict -F "file=@loadtest/images/glass_01.jpg"
```
→ sans token : **401 refusé**.

```bash
curl -X POST http://localhost/api/predict -H "X-API-Key: <TOKEN>" -F "file=@loadtest/images/glass_01.jpg"
```
→ avec token : la prédiction.

```bash
curl http://localhost/api/admin/usage -H "X-Admin-Key: <ADMIN_TOKEN>"
```
→ nombre de requêtes et latence moyenne **par utilisateur**.

---

## 6. Niveau 2 — créer la VM AWS avec Terraform

```bash
aws configure
```
→ enregistre ta clé d'accès AWS (IAM ▸ Utilisateurs ▸ Créer une clé d'accès). Région : `eu-west-3`.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/trashnet -N ""
```
→ crée une paire de clés SSH pour se connecter à la VM.

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
curl ifconfig.me
```
→ affiche ton IP publique ; mets-la dans `terraform.tfvars` (`my_ip = "x.x.x.x/32"`).

```bash
terraform init
```
→ télécharge le plugin AWS.

```bash
terraform apply
```
→ crée la VM (m7i-flex.large, offre gratuite), le pare-feu et une IP fixe. Tape `yes`. Note l'`app_url` affichée.

> 💰 Couvert par les crédits de l'offre gratuite. **Pense à `terraform destroy` après la soutenance.**

---

## 7. Niveau 1 — déployer en une commande

```bash
cd ..
chmod +x scripts/deploy.sh
./scripts/deploy.sh <IP_DE_LA_VM>
```
→ copie le code sur la VM, lance `docker compose up` là-bas, vérifie que l'API répond.

Ensuite, pour mettre le modèle dans le MLflow de la VM :
```bash
MLFLOW_TRACKING_URI=http://<IP>:5050 python training/train.py --promote
ssh -i ~/.ssh/trashnet ubuntu@<IP> "cd trashnet && docker compose restart api"
```
→ entraîne + enregistre dans le MLflow de production, puis les 3 API rechargent le modèle `champion`.

### Pipeline CD (déploiement automatique à chaque push)

Dans GitHub ▸ Settings ▸ Secrets ▸ Actions, ajoute :

| Secret | Valeur |
|---|---|
| `VM_HOST` | IP de la VM |
| `SSH_PRIVATE_KEY` | contenu de `~/.ssh/trashnet` |
| `ADMIN_TOKEN` | ton token admin |
| `POSTGRES_PASSWORD` | mot de passe de la base |

```bash
git add . && git commit -m "deploy" && git push
```
→ GitHub lance les tests, puis déploie tout seul sur la VM (onglet **Actions**).

---

## 8. Niveau 2 — mettre à jour le modèle avec MLflow

1. Ré-entraîner → nouvelle version dans MLflow (v2, v3…).
2. Comparer les runs dans l'UI MLflow (accuracy, taille, latence).
3. Mettre l'alias `champion` sur la meilleure version (UI MLflow ou `--promote`).
4. `docker compose restart api` → la production utilise la nouvelle version.
5. Retour arrière = remettre l'alias sur l'ancienne version.

---

## 9. Niveau 2 — détection de data drift

Pour chaque image reçue, l'API calcule luminosité, contraste, couleurs, saturation.
Elle les compare aux images d'entraînement avec un test statistique (Kolmogorov-Smirnov).
Si au moins la moitié des mesures sont trop différentes → **DRIFT**.

```bash
python scripts/simulate_drift.py --url http://<IP>/api --token <TOKEN> --admin <ADMIN_TOKEN>
```
→ envoie 60 images normales (OK) puis 60 images assombries (DRIFT).

---

## 10. Niveau 1 — test de charge

```bash
pip install locust
export LOCUST_TOKEN=<TOKEN>
locust -f loadtest/locustfile.py --host http://<IP>/api --headless -u 50 -r 5 -t 3m --csv results/locust
```
→ simule 50 utilisateurs (5 nouveaux/seconde) pendant 3 min. Résultats dans `results/locust_stats.csv`.

```bash
python scripts/make_charts.py
```
→ regénère les graphiques du PowerPoint à partir de **tes** résultats.

---

## 11. Niveau 3 — quantization + scaling horizontal

**Quantization** : faite automatiquement par `train.py` (voir `results/training_summary.json` → `bench`).

**Scaling horizontal** : 3 copies de l'API, Nginx répartit les requêtes.
```bash
docker compose up -d --scale api=5 && docker compose restart nginx
```
→ passe à 5 copies de l'API (le header `X-Instance` montre quelle copie a répondu).

```bash
for i in 1 2 3 4 5 6; do curl -s -o /dev/null -D - http://<IP>/api/health | grep -i x-instance; done
```
→ on voit les requêtes tourner entre les conteneurs.

---

## 12. Commandes utiles

| Commande | Effet |
|---|---|
| `docker compose logs -f api` | voir les logs de l'API en direct |
| `docker compose down` | tout arrêter |
| `pytest -q tests` | lancer les tests |
| `terraform destroy` | supprimer la VM AWS |
