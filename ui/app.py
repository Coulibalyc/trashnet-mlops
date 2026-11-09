"""Interface web Streamlit : on prend une photo, l'IA dit dans quelle poubelle la jeter."""
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
BINS = {"cardboard": ("Carton", "🟡 Bac jaune"), "paper": ("Papier", "🟡 Bac jaune"),
        "plastic": ("Plastique", "🟡 Bac jaune"), "metal": ("Métal", "🟡 Bac jaune"),
        "glass": ("Verre", "🟢 Borne à verre"), "trash": ("Ordures", "⚫ Bac gris")}

st.set_page_config(page_title="TrashNet", page_icon="♻️", layout="centered")
st.title("♻️ TrashNet — tri des déchets")

with st.sidebar:
    token = st.text_input("Token utilisateur", type="password")
    admin_key = st.text_input("Clé admin (optionnel)", type="password")

tab1, tab2, tab3 = st.tabs(["Classer un déchet", "Mon usage", "Admin"])

with tab1:
    img = st.camera_input("Prendre une photo") or st.file_uploader("…ou envoyer une image",
                                                                    type=["jpg", "jpeg", "png"])
    if img and token:
        r = requests.post(f"{API}/predict", headers={"X-API-Key": token},
                          files={"file": ("img.jpg", img.getvalue())}, timeout=30)
        if r.ok:
            res = r.json()
            name, bin_ = BINS[res["label"]]
            c1, c2 = st.columns(2)
            c1.image(img, use_container_width=True)
            c2.metric("Catégorie", name, f"{res['confidence']:.0%} de confiance")
            c2.subheader(bin_)
            c2.caption(f"{res['latency_ms']} ms · modèle {res['model_version']} · {res['instance']}")
            probs = pd.Series(res["probabilities"]).rename(lambda k: BINS[k][0]).sort_values()
            st.bar_chart(probs, horizontal=True)
        else:
            st.error(r.json().get("detail", r.text))
    elif img:
        st.warning("Entrez votre token dans la barre de gauche.")

with tab2:
    if token:
        r = requests.get(f"{API}/me/usage", headers={"X-API-Key": token}, timeout=10)
        st.dataframe(r.json() if r.ok else [], use_container_width=True)

with tab3:
    if admin_key:
        h = {"X-Admin-Key": admin_key}
        new = st.text_input("Créer un utilisateur")
        if st.button("Créer") and new:
            st.json(requests.post(f"{API}/admin/users", json={"name": new}, headers=h, timeout=10).json())
        usage = requests.get(f"{API}/admin/usage", headers=h, timeout=10)
        if usage.ok and usage.json():
            df = pd.DataFrame(usage.json()).set_index("user")
            st.subheader("Requêtes par utilisateur")
            st.bar_chart(df["requests"])
            st.dataframe(df, use_container_width=True)
        d = requests.get(f"{API}/admin/drift", headers=h, timeout=10)
        if d.ok:
            d = d.json()
            st.subheader(f"Data drift : {d['status']}")
            if "features" in d:
                st.dataframe(pd.DataFrame(d["features"]).T, use_container_width=True)
