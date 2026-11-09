"""Génère tous les graphiques de la présentation à partir des fichiers de results/.

    python scripts/make_charts.py

Fichiers lus (ceux qui manquent sont simplement ignorés) :
  results/training_summary.json        <- training/train.py
  results/locust_1rep_stats*.csv       <- test de charge avec 1 API   (API_REPLICAS=1)
  results/locust_3rep_stats*.csv       <- test de charge avec 3 API   (API_REPLICAS=3)
  results/drift_demo.json              <- scripts/simulate_drift.py
  results/usage.json                   <- curl .../admin/usage > results/usage.json
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

R = Path(__file__).resolve().parents[1] / "results"
OUT = R / "charts"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
INK, INK2, GRID, BG = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
FR = {"cardboard": "Carton", "glass": "Verre", "metal": "Métal",
      "paper": "Papier", "plastic": "Plastique", "trash": "Ordures"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 13, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.facecolor": BG,
    "figure.facecolor": BG, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.dpi": 200, "savefig.bbox": "tight"})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)
    print("ok", name)


def bar_labels(ax, bars, fmt="{:.0f}", horizontal=False):
    for b in bars:
        v = b.get_width() if horizontal else b.get_height()
        if horizontal:
            ax.text(v, b.get_y() + b.get_height() / 2, " " + fmt.format(v), va="center", color=INK, fontsize=12)
        else:
            ax.text(b.get_x() + b.get_width() / 2, v, fmt.format(v), ha="center", va="bottom", color=INK, fontsize=12)


def training():
    p = R / "training_summary.json"
    if not p.exists():
        return
    s = json.loads(p.read_text())
    classes = s["classes"]
    cm = np.array(s["confusion_matrix"])

    # 1) Nombre d'images par classe
    counts = cm.sum(1) / s["splits"]["test"] * sum(s["splits"].values())
    fig, ax = plt.subplots(figsize=(7, 4))
    order = np.argsort(counts)
    bars = ax.barh([FR[classes[i]] for i in order], counts[order], color=BLUE, height=0.6)
    bar_labels(ax, bars, horizontal=True)
    ax.set_xlabel("images")
    ax.grid(axis="y", visible=False)
    save(fig, "dataset")

    # 2) Courbes d'apprentissage
    h = s["history"]
    ep = [x["epoch"] for x in h]
    n_head = s.get("epochs_head") or len(ep) // 2
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axvspan(n_head + 0.5, ep[-1] + 0.3, color="#f3f2ef", zorder=0)
    ax.text(n_head + 0.7, 0.42, "fine-tuning", color=INK2, fontsize=11)
    ax.plot(ep, [x["train_acc"] for x in h], color=BLUE, lw=2.2, marker="o", ms=6, label="Entraînement")
    ax.plot(ep, [x["val_acc"] for x in h], color=ORANGE, lw=2.2, marker="o", ms=6, label="Validation")
    ax.set_ylim(0.4, 1.0)
    ax.set_xlabel("époque")
    ax.set_ylabel("accuracy")
    ax.set_xticks(ep)
    ax.legend(loc="lower right")
    save(fig, "curves")

    # 3) Matrice de confusion
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    norm = cm / cm.sum(1, keepdims=True)
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    labels = [FR[c] for c in classes]
    ax.set_xticks(range(len(classes)), labels, rotation=35, ha="right")
    ax.set_yticks(range(len(classes)), labels)
    ax.set_xlabel("prédit")
    ax.set_ylabel("réel")
    ax.grid(False)
    for i in range(len(classes)):
        for j in range(len(classes)):
            if cm[i, j]:
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=12,
                        color="white" if norm[i, j] > 0.55 else INK)
    save(fig, "confusion")

    # 4) F1 par classe
    f1 = s["f1_per_class"]
    items = sorted(f1.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh([FR[k] for k, _ in items], [v for _, v in items], color=BLUE, height=0.6)
    bar_labels(ax, bars, "{:.2f}", horizontal=True)
    ax.set_xlim(0, 1.08)
    ax.set_xlabel("F1-score (test)")
    ax.grid(axis="y", visible=False)
    save(fig, "f1")

    # 5) Quantization : fp32 vs int8, trois petits graphiques côte à côte
    b = s["bench"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    for ax, (key, title, fmt) in zip(axes, [("size_mb", "Taille (Mo)", "{:.1f}"),
                                            ("latency_ms", "Latence / image (ms)", "{:.1f}"),
                                            ("accuracy", "Accuracy test", "{:.1%}")]):
        vals = [b["fp32"][key], b["int8"][key]]
        bars = ax.bar(["FP32", "INT8"], vals, color=[INK2, BLUE], width=0.55)
        bar_labels(ax, bars, fmt)
        ax.set_title(title, color=INK, fontsize=13, pad=12)
        ax.set_ylim(0, max(vals) * 1.2)
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="y", labelleft=False, length=0)
    save(fig, "quantization")


def read_locust(prefix):
    stats = R / f"{prefix}_stats.csv"
    hist = R / f"{prefix}_stats_history.csv"
    if not stats.exists():
        return None
    rows = {r["Name"]: r for r in csv.DictReader(open(stats))}
    agg = rows["Aggregated"]
    pred = rows.get("/predict", agg)
    history = list(csv.DictReader(open(hist))) if hist.exists() else []
    history = [h for h in history if h["Name"] == "Aggregated"]
    return {"rps": float(agg["Requests/s"]), "fail": float(agg["Failure Count"]),
            "n": int(agg["Request Count"]),
            "p50": float(pred["50%"]), "p95": float(pred["95%"]), "p99": float(pred["99%"]),
            "history": history}


def load():
    runs = {k: read_locust(f"locust_{k}rep") for k in ("1", "3")}
    runs = {k: v for k, v in runs.items() if v}
    if not runs:
        return
    main = runs.get("3") or next(iter(runs.values()))

    # 6) Débit et utilisateurs dans le temps
    h = main["history"]
    if h:
        t0 = int(h[0]["Timestamp"])
        t = [int(x["Timestamp"]) - t0 for x in h]
        fig, axes = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True)
        axes[0].plot(t, [float(x["Requests/s"]) for x in h], color=BLUE, lw=2)
        axes[0].set_ylabel("requêtes / s")
        axes[1].plot(t, [float(x["95%"]) if x["95%"] != "N/A" else np.nan for x in h], color=ORANGE, lw=2)
        axes[1].set_ylabel("latence p95 (ms)")
        axes[1].set_xlabel("secondes")
        save(fig, "load_timeline")

    # 7) Scaling : 1 API vs 3 API
    if len(runs) == 2:
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
        for ax, (key, title, fmt) in zip(axes, [("rps", "Débit (req/s)", "{:.0f}"),
                                                ("p50", "Latence médiane (ms)", "{:.0f}"),
                                                ("p95", "Latence p95 (ms)", "{:.0f}")]):
            vals = [runs["1"][key], runs["3"][key]]
            bars = ax.bar(["1 API", "3 API"], vals, color=[INK2, BLUE], width=0.55)
            bar_labels(ax, bars, fmt)
            ax.set_title(title, color=INK, fontsize=13, pad=12)
            ax.set_ylim(0, max(vals) * 1.2)
            ax.grid(axis="x", visible=False)
            ax.tick_params(axis="y", labelleft=False, length=0)
        save(fig, "scaling")
    summary = {k: {m: v for m, v in r.items() if m != "history"} for k, r in runs.items()}
    if h:   # courbe dans le temps (1 point toutes les 5 s) pour le PowerPoint
        summary["timeline"] = [{"t": int(x["Timestamp"]) - t0, "rps": float(x["Requests/s"]),
                                "users": int(x["User Count"]),
                                "p95": float(x["95%"]) if x["95%"] != "N/A" else None}
                               for x in h[::5]]
    (R / "load_summary.json").write_text(json.dumps(summary, indent=1))


def mlflow_versions():
    """Exporte la liste des versions du modèle (Model Registry) pour le PowerPoint."""
    import os
    try:
        from mlflow import MlflowClient
        os.environ.setdefault("MLFLOW_TRACKING_URI", "http://localhost:5050")
        c = MlflowClient()
        out = []
        for v in sorted(c.search_model_versions("name='trashnet-classifier'"), key=lambda v: int(v.version)):
            m = c.get_run(v.run_id).data
            out.append({"version": int(v.version), "aliases": list(v.aliases),
                        "model": m.params.get("model", ""), "fp32_acc": m.metrics.get("fp32_accuracy"),
                        "epochs": int(m.params.get("epochs_head", 0)) + int(m.params.get("epochs_finetune", 0)),
                        "test_acc": m.metrics.get("int8_accuracy"), "size_mb": m.metrics.get("int8_size_mb"),
                        "latency_ms": m.metrics.get("int8_latency_ms")})
        (R / "mlflow_versions.json").write_text(json.dumps(out, indent=1))
        print("ok mlflow_versions")
    except Exception as e:
        print("MLflow non joignable, versions ignorées :", e)


def drift():
    p = R / "drift_demo.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    feats = list(d["normal"]["features"])
    names = {"brightness": "Luminosité", "contrast": "Contraste", "red": "Rouge",
             "green": "Vert", "blue": "Bleu", "saturation": "Saturation"}
    x = np.arange(len(feats))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    floor = 1e-12
    for i, (key, col, lab) in enumerate([("normal", BLUE, "Images normales"),
                                         ("dark", ORANGE, "Images sombres")]):
        vals = [max(d[key]["features"][f]["p_value"], floor) for f in feats]
        ax.bar(x + (i - 0.5) * 0.36, vals, 0.34, color=col, label=lab)
    ax.axhline(0.05, color=INK, lw=1.2, ls="--")
    ax.text(len(feats) - 0.5, 0.07, "seuil 0,05 : en dessous = drift", ha="right", color=INK, fontsize=11)
    ax.set_yscale("log")
    ax.set_ylabel("p-value (échelle log)")
    ax.set_xticks(x, [names[f] for f in feats])
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", ncol=2)
    save(fig, "drift")


def usage():
    p = R / "usage.json"
    if not p.exists():
        return
    u = sorted(json.loads(p.read_text()), key=lambda r: r["requests"])
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bars = ax.barh([r["user"] for r in u], [r["requests"] for r in u], color=BLUE, height=0.55)
    bar_labels(ax, bars, horizontal=True)
    ax.set_xlabel("requêtes")
    ax.grid(axis="y", visible=False)
    save(fig, "usage")


if __name__ == "__main__":
    training()
    load()
    drift()
    usage()
    mlflow_versions()
