// Construit la présentation finale à partir des fichiers de results/.
//   cd presentation && npm install && node build_deck.js
// Relancez-le après vos propres tests sur AWS : les graphiques se mettent à jour.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const fa6 = require("react-icons/fa6");

const R = path.join(__dirname, "..", "results");
const load = (f, d = null) => (fs.existsSync(path.join(R, f)) ? JSON.parse(fs.readFileSync(path.join(R, f))) : d);
const train = load("training_summary.json");
const loadT = load("load_summary.json", {});
const drift = load("drift_demo.json");
const usage = load("usage.json", []);
const sec = load("security_checks.json", []);
const versions = load("mlflow_versions.json", []);
const PARAMS = process.env.PARAMS || "3,4 M";
const b0cmp = load("model_comparison_b0.json");
const MEASURED = process.env.MEASURED_ON || "mesuré en local (2 vCPU)";

// ---------- Thème : vert recyclage ----------
const THEME = {
  name: "TrashNet", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "1B1F1B", lt1: "FFFFFF", dk2: "1F3D20", lt2: "EEF4E8",
    accent1: "2C6E2F", accent2: "E07A2E", accent3: "97BC62", accent4: "6B7069",
    accent5: "C9DDB4", accent6: "B23A3A", hlink: "2C6E2F", folHlink: "6B7069" },
};
const HEX = THEME.colors;
const GREEN = HEX.accent1, ORANGE = HEX.accent2, MOSS = HEX.accent3, GREY = HEX.accent4, TINT = HEX.lt2;
const INK = HEX.dk1, MUTED = "5A6058", GRID = "E2E6DE";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "TrashNet MLOps";
const C = pres.SchemeColor;
const W = 13.333;

pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.5, w: 8.5, h: 1.4, fontSize: 54, bold: true, color: "FFFFFF", valign: "bottom", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.0, w: 8.5, h: 1.2, fontSize: 22, color: HEX.accent5, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 32, bold: true, color: HEX.dk2, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "TrashNet · Projet MLOps", options: { x: 0.6, y: 7.0, w: 5, h: 0.3, fontSize: 10, color: HEX.accent4, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: GREY, align: "right" },
});

// ---------- Aides ----------
async function icon(Comp, color = "FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
async function iconCircle(slide, Comp, x, y, d, bg = GREEN, fg = "FFFFFF", name = "icon") {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg }, objectName: name + "-circle" });
  const pad = d * 0.24;
  slide.addImage({ data: await icon(Comp, fg), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name });
}
const txt = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, color: INK, fontSize: 16, ...o });
function card(slide, x, y, w, h, fill = TINT, name = "card") {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill }, objectName: name });
}
function stat(slide, value, label, x, y, w, color = GREEN, size = 54) {
  txt(slide, value, { x, y, w, h: 0.95, fontSize: size, bold: true, color, valign: "bottom" });
  txt(slide, label, { x, y: y + 1.0, w, h: 0.5, fontSize: 15, color: MUTED, valign: "top" });
}
const chartBase = (o = {}) => ({
  catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontSize: 13, valAxisLabelFontSize: 12,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", titleFontFace: "+mn-lt",
  valGridLine: { color: GRID, size: 0.75 }, catGridLine: { style: "none" },
  catAxisLineShow: false, valAxisLineShow: false, dataLabelColor: INK, dataLabelFontSize: 12,
  showLegend: false, legendColor: MUTED, legendFontSize: 13, legendPos: "t", titleColor: INK, titleFontSize: 15, ...o,
});
const FR = { cardboard: "Carton", glass: "Verre", metal: "Métal", paper: "Papier", plastic: "Plastique", trash: "Ordures" };
const pct = (v, d = 1) => (v * 100).toFixed(d).replace(".", ",") + " %";
const num = (v, d = 1) => v.toFixed(d).replace(".", ",");
const content = (title, section) => {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
};
const tableHead = (cells) => cells.map((t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } }));

(async () => {
  const classes = train.classes;
  const cm = train.confusion_matrix;
  const total = Object.values(train.splits).reduce((a, b) => a + b, 0);
  const counts = classes.map((_, i) => Math.round((cm[i].reduce((a, b) => a + b, 0) / train.splits.test) * total));
  const b = train.bench;

  // ===== 1. Titre =====
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  s.addText("TrashNet", { placeholder: "title" });
  s.addText("Tri des déchets par IA — de l'entraînement à la production", { placeholder: "body" });
  await iconCircle(s, fa.FaRecycle, 9.9, 2.3, 2.6, MOSS, HEX.dk2, "logo");
  txt(s, "Projet MLOps · M1 Data Engineering & IA · EFREI Paris", { x: 0.8, y: 6.4, w: 9, h: 0.4, fontSize: 14, color: HEX.accent5 });

  // ===== 2. Le sujet =====
  s = content("Une photo → la bonne poubelle", "Introduction");
  const icons = { cardboard: fa.FaBoxOpen, glass: fa.FaWineBottle, metal: fa6.FaJarWheat, paper: fa.FaNewspaper, plastic: fa6.FaBottleWater, trash: fa.FaTrashAlt };
  const bins = { cardboard: "Bac jaune", glass: "Borne à verre", metal: "Bac jaune", paper: "Bac jaune", plastic: "Bac jaune", trash: "Bac gris" };
  for (let i = 0; i < 6; i++) {
    const c = classes[i], col = i % 3, row = Math.floor(i / 3);
    const x = 0.6 + col * 4.1, y = 1.55 + row * 2.6;
    card(s, x, y, 3.8, 2.3, TINT, "card-" + c);
    await iconCircle(s, icons[c], x + 0.35, y + 0.45, 1.3, c === "trash" ? GREY : GREEN, "FFFFFF", "icon-" + c);
    txt(s, FR[c], { x: x + 1.9, y: y + 0.45, w: 1.8, h: 0.55, fontSize: 24, bold: true });
    txt(s, `${counts[i]} photos`, { x: x + 1.9, y: y + 1.0, w: 1.8, h: 0.4, fontSize: 15, color: MUTED });
    txt(s, bins[c], { x: x + 1.9, y: y + 1.4, w: 1.8, h: 0.4, fontSize: 15, color: GREEN, bold: true });
  }

  // ===== 3. Données =====
  pres.addSection({ title: "Modèle" });
  s = content("Les données : TrashNet", "Modèle");
  const order = counts.map((v, i) => i).sort((a, b) => counts[a] - counts[b]);
  s.addChart(pres.charts.BAR, [{ name: "Images", labels: order.map((i) => FR[classes[i]]), values: order.map((i) => counts[i]) }],
    chartBase({ x: 0.6, y: 1.4, w: 6.6, h: 5.3, barDir: "bar", chartColors: [GREEN], barGapWidthPct: 45,
      showValue: true, dataLabelPosition: "outEnd", showTitle: true, title: "Images par classe", valAxisHidden: true, valGridLine: { style: "none" } }));
  s.addTable([tableHead(["Jeu", "Images", "Part"]),
    ...["train", "val", "test"].map((k) => [{ text: { train: "Entraînement", val: "Validation", test: "Test" }[k] }, { text: String(train.splits[k]) }, { text: pct(train.splits[k] / total, 0) }])],
    { x: 7.8, y: 1.6, w: 4.9, colW: [2.3, 1.3, 1.3], fontSize: 16, color: INK, border: { type: "solid", pt: 0.75, color: GRID }, rowH: 0.5, align: "left", valign: "middle" });
  card(s, 7.8, 4.2, 4.9, 2.2, TINT, "callout");
  stat(s, `${total}`, "photos réelles, fond blanc, 512 × 384 px", 8.15, 4.3, 4.3, GREEN, 48);
  txt(s, `« Ordures » : seulement ${counts[classes.indexOf("trash")]} images`, { x: 8.15, y: 5.85, w: 4.3, h: 0.4, fontSize: 14, color: ORANGE, bold: true });

  // ===== 4. Modèle =====
  s = content("Le modèle : transfer learning", "Modèle");
  const steps = [[fa.FaCamera, "Photo", "224 × 224 px"], [fa.FaBrain, "EfficientNet-Lite0", "pré-entraîné ImageNet"], [fa.FaLayerGroup, "Couche finale", "6 neurones"], [fa.FaChartBar, "Probabilités", "6 classes"]];
  for (let i = 0; i < 4; i++) {
    const x = 0.6 + i * 3.15;
    card(s, x, 1.6, 2.75, 2.6, i === 1 ? GREEN : TINT, "step-" + i);
    await iconCircle(s, steps[i][0], x + 0.85, 1.85, 1.05, i === 1 ? "FFFFFF" : GREEN, i === 1 ? GREEN : "FFFFFF", "step-icon-" + i);
    txt(s, steps[i][1], { x: x + 0.15, y: 3.05, w: 2.45, h: 0.5, fontSize: 19, bold: true, align: "center", color: i === 1 ? "FFFFFF" : INK });
    txt(s, steps[i][2], { x: x + 0.15, y: 3.5, w: 2.45, h: 0.45, fontSize: 14, align: "center", color: i === 1 ? HEX.accent5 : MUTED });
    if (i < 3) s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: x + 2.83, y: 2.75, w: 0.25, h: 0.3, rotate: 90, fill: { color: MOSS }, line: { color: MOSS } });
  }
  const nEp = train.history.length, nHead = train.epochs_head || Math.floor(nEp / 2);
  stat(s, PARAMS, "paramètres", 0.9, 4.75, 3.5);
  stat(s, String(nEp), `époques (${nHead} tête + ${nEp - nHead} fine-tuning)`, 4.55, 4.75, 4.2);
  stat(s, "ONNX", "export sans PyTorch en prod", 9.0, 4.75, 3.7);

  // ===== 5. Apprentissage =====
  s = content("Apprentissage", "Modèle");
  const ep = train.history.map((h) => String(h.epoch));
  s.addChart(pres.charts.LINE, [
    { name: "Entraînement", labels: ep, values: train.history.map((h) => +(h.train_acc * 100).toFixed(1)) },
    { name: "Validation", labels: ep, values: train.history.map((h) => +(h.val_acc * 100).toFixed(1)) }],
    chartBase({ x: 0.6, y: 1.4, w: 8.0, h: 5.3, chartColors: [GREEN, ORANGE], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 8,
      showLegend: true, valAxisMinVal: 40, valAxisMaxVal: 100, valAxisLabelFormatCode: '0"%"', showTitle: true, title: "Accuracy par époque (%)",
      showCatAxisTitle: true, catAxisTitle: "époque", catAxisTitleColor: MUTED, catAxisTitleFontSize: 12 }));
  card(s, 9.0, 1.6, 3.7, 4.9, TINT, "result-card");
  stat(s, pct(train.test_acc), "accuracy sur le test (jamais vu)", 9.3, 1.85, 3.2, GREEN, 50);
  const f1m = Object.values(train.f1_per_class).reduce((a, c) => a + c, 0) / classes.length;
  stat(s, num(f1m, 2), "F1-score moyen", 9.3, 4.15, 3.2, GREEN, 50);

  // ===== 6. Confusion =====
  s = content("Où le modèle se trompe", "Modèle");
  const mix = (t) => { // blanc -> vert foncé
    const a = [255, 255, 255], z = [0x2c, 0x6e, 0x2f];
    return a.map((v, k) => Math.round(v + (z[k] - v) * t).toString(16).padStart(2, "0")).join("").toUpperCase();
  };
  const head = [{ text: "réel ↓  prédit →", options: { fontSize: 11, color: MUTED } }, ...classes.map((c) => ({ text: FR[c], options: { bold: true, fontSize: 12, align: "center" } }))];
  const rows = classes.map((c, i) => {
    const sum = cm[i].reduce((a, v) => a + v, 0);
    return [{ text: FR[c], options: { bold: true, fontSize: 13 } }, ...cm[i].map((v) => {
      const t = v / sum;
      return { text: v ? String(v) : "", options: { fill: { color: mix(t) }, color: t > 0.55 ? "FFFFFF" : INK, align: "center", fontSize: 14, bold: t > 0.55 } };
    })];
  });
  s.addTable([head, ...rows], { x: 0.6, y: 1.55, w: 7.0, colW: [1.6, ...Array(6).fill(0.9)], rowH: 0.7, color: INK, valign: "middle", border: { type: "solid", pt: 1, color: "FFFFFF" } });
  const f1 = Object.entries(train.f1_per_class).sort((a, b) => a[1] - b[1]);
  s.addChart(pres.charts.BAR, [{ name: "F1", labels: f1.map(([k]) => FR[k]), values: f1.map(([, v]) => +v.toFixed(2)) }],
    chartBase({ x: 8.0, y: 1.4, w: 4.75, h: 5.3, barDir: "bar", chartColors: [GREEN], barGapWidthPct: 45, showValue: true, dataLabelPosition: "outEnd",
      dataLabelFormatCode: "0.00", valAxisHidden: true, valGridLine: { style: "none" }, valAxisMaxVal: 1.1, valAxisMinVal: 0, showTitle: true, title: "F1-score par classe" }));

  // ===== 7. Architecture =====
  pres.addSection({ title: "Production" });
  s = content("Architecture en production", "Production");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.1, y: 1.45, w: 9.65, h: 5.25, rectRadius: 0.15, fill: { color: TINT }, line: { color: MOSS, width: 1.5, dashType: "dash" }, objectName: "vm" });
  txt(s, "VM AWS EC2 · m7i-flex.large · créée par Terraform", { x: 3.35, y: 1.55, w: 7, h: 0.4, fontSize: 14, bold: true, color: GREEN });
  const box = async (Ic, label, sub, x, y, w = 2.2, fill = "FFFFFF") => {
    card(s, x, y, w, 1.0, fill, "box-" + label);
    await iconCircle(s, Ic, x + 0.15, y + 0.2, 0.6, GREEN, "FFFFFF", "box-icon-" + label);
    txt(s, label, { x: x + 0.85, y: y + 0.15, w: w - 0.9, h: 0.4, fontSize: 15, bold: true });
    txt(s, sub, { x: x + 0.85, y: y + 0.52, w: w - 0.9, h: 0.35, fontSize: 11, color: MUTED });
  };
  const arrow = (x1, y1, x2, y2) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, flipV: y2 < y1, line: { color: GREY, width: 1.5, endArrowType: "triangle" } });
  await box(fa.FaUser, "Utilisateur", "navigateur / API", 0.6, 3.55, 2.2, TINT);
  await box(fa.FaRandom, "Nginx", "load balancer :80", 3.5, 3.55);
  await box(fa.FaDesktop, "Streamlit", "interface web", 6.4, 2.1);
  for (let i = 0; i < 3; i++) await box(fa.FaBolt, `API #${i + 1}`, "FastAPI + ONNX", 6.4, 3.35 + i * 1.1);
  await box(fa.FaDatabase, "Postgres", "tokens, usage, drift", 9.9, 3.35, 2.55);
  await box(fa.FaFlask, "MLflow", "versions du modèle", 9.9, 4.95, 2.55);
  arrow(2.8, 4.05, 3.5, 4.05);
  arrow(5.7, 3.85, 6.4, 2.6);
  for (let i = 0; i < 3; i++) arrow(5.7, 4.05, 6.4, 3.85 + i * 1.1);
  arrow(8.6, 4.4, 9.9, 3.85);
  arrow(8.6, 4.95, 9.9, 5.45);
  await iconCircle(s, fa.FaGithub, 0.6, 5.55, 0.7, HEX.dk2, "FFFFFF", "gh");
  txt(s, "GitHub Actions\ndéploie à chaque push", { x: 1.4, y: 5.5, w: 1.7, h: 0.8, fontSize: 12, color: MUTED });

  // ===== 8. Exigences =====
  s = content("Exigences couvertes", "Production");
  const reqs = [
    ["0", "Tout se lance en 1 commande, en conteneurs", "docker compose up -d --build (7 conteneurs)"],
    ["1", "Déploiement automatique sur une VM", "scripts/deploy.sh + pipeline GitHub Actions"],
    ["1", "Accès protégé par token", "header X-API-Key, tokens hachés en base"],
    ["1", "Usage suivi par utilisateur", "table predictions + route /admin/usage"],
    ["1", "Test de charge", "Locust : 3 scénarios"],
    ["2", "VM créée automatiquement", "Terraform (EC2, pare-feu, IP fixe)"],
    ["2", "Interface utilisateur", "Streamlit : photo, usage, admin"],
    ["2", "Détection de data drift", "test KS sur 6 mesures d'image"],
    ["2", "Versionnage MLflow", "Model Registry + alias champion"],
    ["3", "Quantization", "ONNX int8 (statique, par canal)"],
    ["3", "Scaling horizontal", "3 API derrière Nginx"],
  ];
  s.addTable([tableHead(["Niv.", "Exigence", "Notre solution", "✓"]),
    ...reqs.map((r) => [{ text: r[0], options: { bold: true, color: GREEN, align: "center" } }, { text: r[1] }, { text: r[2], options: { color: MUTED } }, { text: "✓", options: { color: GREEN, bold: true, align: "center" } }])],
  { x: 0.6, y: 1.4, w: 12.1, colW: [0.8, 5.0, 5.6, 0.7], fontSize: 14, color: INK, rowH: 0.43, valign: "middle", border: { type: "solid", pt: 0.75, color: GRID } });

  // ===== 9. Sécurité =====
  s = content("Sécurité par token et suivi de l'usage", "Production");
  if (sec.length) {
    s.addTable([tableHead(["Requête", "Attendu", "Obtenu"]),
      ...sec.map((r) => [{ text: r.case }, { text: String(r.expected), options: { align: "center" } },
        { text: `${r.got} ${r.ok ? "✓" : "✗"}`, options: { align: "center", bold: true, color: r.ok ? GREEN : HEX.accent6 } }])],
    { x: 0.6, y: 1.5, w: 6.6, colW: [4.4, 1.1, 1.1], fontSize: 14, color: INK, rowH: 0.55, valign: "middle", border: { type: "solid", pt: 0.75, color: GRID } });
  }
  if (usage.length) {
    const u = [...usage].sort((a, b) => a.requests - b.requests);
    s.addChart(pres.charts.BAR, [{ name: "Requêtes", labels: u.map((r) => r.user), values: u.map((r) => r.requests) }],
      chartBase({ x: 7.6, y: 1.4, w: 5.15, h: 5.3, barDir: "bar", chartColors: [GREEN], barGapWidthPct: 45, showValue: true, dataLabelPosition: "outEnd",
        valAxisHidden: true, valGridLine: { style: "none" }, showTitle: true, title: "Requêtes par utilisateur" }));
  }

  // ===== 10. Déploiement =====
  s = content("Infrastructure et déploiement automatiques", "Production");
  const cd = [[fa.FaCodeBranch, "git push", "branche main"], [fa.FaCheckCircle, "Tests", "pytest · 5 tests"], [fa.FaUpload, "Copie", "rsync vers la VM"], [fa.FaDocker, "Lancement", "docker compose up"], [fa.FaHeartbeat, "Vérification", "GET /health"]];
  for (let i = 0; i < 5; i++) {
    const x = 0.6 + i * 2.48;
    await iconCircle(s, cd[i][0], x + 0.6, 1.55, 0.95, GREEN, "FFFFFF", "cd-" + i);
    txt(s, cd[i][1], { x, y: 2.6, w: 2.15, h: 0.45, fontSize: 17, bold: true, align: "center" });
    txt(s, cd[i][2], { x, y: 3.0, w: 2.15, h: 0.4, fontSize: 13, color: MUTED, align: "center" });
    if (i < 4) s.addShape(pres.shapes.LINE, { x: x + 1.7, y: 2.03, w: 0.85, h: 0, line: { color: MOSS, width: 2, endArrowType: "triangle" } });
  }
  txt(s, "Terraform : terraform apply crée tout en ~2 min", { x: 0.6, y: 3.75, w: 12, h: 0.45, fontSize: 18, bold: true, color: GREEN });
  s.addTable([tableHead(["Ressource AWS", "Rôle", "Détail"]),
    [{ text: "aws_instance" }, { text: "la VM" }, { text: "Ubuntu 24.04 · m7i-flex.large · Docker installé au démarrage" }],
    [{ text: "aws_security_group" }, { text: "pare-feu" }, { text: "80 public · 22 SSH · 5050 MLflow (mon IP seulement)" }],
    [{ text: "aws_eip" }, { text: "IP fixe" }, { text: "l'adresse ne change pas au redémarrage" }],
    [{ text: "aws_key_pair" }, { text: "accès SSH" }, { text: "clé ed25519, utilisée aussi par la CD" }]],
  { x: 0.6, y: 4.3, w: 12.1, colW: [2.8, 1.8, 7.5], fontSize: 14, color: INK, rowH: 0.48, valign: "middle", border: { type: "solid", pt: 0.75, color: GRID } });

  // ===== 11. MLflow =====
  pres.addSection({ title: "MLOps" });
  s = content("Versionnage et mise à jour avec MLflow", "MLOps");
  if (versions.length) {
    s.addTable([tableHead(["Version", "Modèle", "Époques", "Accuracy int8", "Taille", "Alias"]),
      ...versions.map((v) => [{ text: "v" + v.version, options: { bold: true } }, { text: (v.model || "").replace("efficientnet-", "EffNet-").replace("lite0", "Lite0").replace("b0", "B0") },
        { text: String(v.epochs), options: { align: "center" } },
        { text: v.test_acc != null ? pct(v.test_acc) : "–", options: { align: "center" } }, { text: v.size_mb != null ? num(v.size_mb) + " Mo" : "–", options: { align: "center" } },
        { text: v.aliases.includes("champion") ? "champion ★" : "", options: { bold: true, color: GREEN, align: "center" } }])],
    { x: 0.6, y: 1.5, w: 7.4, colW: [1.0, 1.6, 1.0, 1.4, 1.1, 1.3], fontSize: 14, color: INK, rowH: 0.55, valign: "middle", border: { type: "solid", pt: 0.75, color: GRID } });
  }
  const flow = [[fa.FaFlask, "Entraîner", "nouvelle version"], [fa.FaBalanceScale, "Comparer", "dans l'UI MLflow"], [fa.FaStar, "Promouvoir", "alias champion"], [fa.FaSyncAlt, "Recharger", "restart api"]];
  for (let i = 0; i < 4; i++) {
    const y = 1.5 + i * 1.3;
    await iconCircle(s, flow[i][0], 8.4, y, 0.85, i === 2 ? ORANGE : GREEN, "FFFFFF", "flow-" + i);
    txt(s, flow[i][1], { x: 9.45, y: y + 0.05, w: 3.2, h: 0.42, fontSize: 18, bold: true });
    txt(s, flow[i][2], { x: 9.45, y: y + 0.45, w: 3.2, h: 0.35, fontSize: 13, color: MUTED });
  }
  txt(s, "Retour arrière = remettre l'alias sur l'ancienne version", { x: 0.6, y: 6.2, w: 7.2, h: 0.4, fontSize: 14, color: MUTED, italic: true });

  // ===== 12. Drift =====
  s = content("Détection de data drift", "MLOps");
  if (drift) {
    const feats = Object.keys(drift.normal.features);
    const names = { brightness: "Luminosité", contrast: "Contraste", red: "Rouge", green: "Vert", blue: "Bleu", saturation: "Saturation" };
    const score = (p) => +Math.min(-Math.log10(Math.max(p, 1e-10)), 10).toFixed(1); // écart : plus haut = plus différent
    s.addChart(pres.charts.BAR, [
      { name: "Images normales", labels: feats.map((f) => names[f]), values: feats.map((f) => score(drift.normal.features[f].p_value)) },
      { name: "Images sombres", labels: feats.map((f) => names[f]), values: feats.map((f) => score(drift.dark.features[f].p_value)) }],
    chartBase({ x: 0.6, y: 1.4, w: 8.4, h: 5.0, barDir: "col", chartColors: [GREEN, ORANGE], barGapWidthPct: 60, showLegend: true,
      valAxisMinVal: 0, valAxisMaxVal: 11, showTitle: true, title: "Écart avec les données d'entraînement (−log10 p-value)" }));
    txt(s, "Drift si l'écart dépasse 1,3 (p < 0,05) sur au moins 3 mesures sur 6", { x: 0.6, y: 6.4, w: 8.4, h: 0.4, fontSize: 13, color: MUTED, italic: true });
    const badge = (label, status, y, col) => {
      card(s, 9.4, y, 3.35, 2.2, TINT, "badge-" + status);
      txt(s, label, { x: 9.7, y: y + 0.25, w: 2.9, h: 0.4, fontSize: 15, color: MUTED });
      txt(s, status, { x: 9.7, y: y + 0.7, w: 2.9, h: 0.8, fontSize: 40, bold: true, color: col });
      txt(s, `${Math.round(((status === "OK" ? drift.normal : drift.dark).drift_share || 0) * 6)}/6 mesures en drift`, { x: 9.7, y: y + 1.5, w: 2.9, h: 0.4, fontSize: 13, color: MUTED });
    };
    badge("Images normales", drift.normal.status, 1.6, GREEN);
    badge("Images assombries", drift.dark.status, 4.2, ORANGE);
  }

  // ===== 12b. Choix du modèle =====
  if (b0cmp) {
    s = content("Pourquoi EfficientNet-Lite0 ?", "MLOps");
    const B = b0cmp["EfficientNet-B0"];
    s.addChart(pres.charts.BAR, [
      { name: "FP32 (normal)", labels: ["EfficientNet-B0", "EfficientNet-Lite0"], values: [+(B.fp32.accuracy * 100).toFixed(1), +(b.fp32.accuracy * 100).toFixed(1)] },
      { name: "INT8 (quantizé)", labels: ["EfficientNet-B0", "EfficientNet-Lite0"], values: [+(B.int8.accuracy * 100).toFixed(1), +(b.int8.accuracy * 100).toFixed(1)] }],
    chartBase({ x: 0.6, y: 1.4, w: 7.6, h: 5.3, barDir: "col", chartColors: [GREY, GREEN], barGapWidthPct: 60, showLegend: true, showValue: true,
      dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 0, valAxisMaxVal: 110, valAxisHidden: true, valGridLine: { style: "none" },
      showTitle: true, title: "Accuracy test (%) avant / après quantization" }));
    const drop = (x) => (x.fp32.accuracy - x.int8.accuracy) * 100;
    card(s, 8.6, 1.6, 4.15, 2.3, TINT, "b0-card");
    txt(s, "EfficientNet-B0", { x: 8.9, y: 1.8, w: 3.6, h: 0.4, fontSize: 15, color: MUTED });
    txt(s, "−" + num(drop(B)) + " pts", { x: 8.9, y: 2.2, w: 3.6, h: 0.8, fontSize: 40, bold: true, color: ORANGE });
    txt(s, "Swish + blocs SE : mal compressés", { x: 8.9, y: 3.1, w: 3.6, h: 0.4, fontSize: 13, color: MUTED });
    card(s, 8.6, 4.2, 4.15, 2.3, TINT, "lite-card");
    txt(s, "EfficientNet-Lite0", { x: 8.9, y: 4.4, w: 3.6, h: 0.4, fontSize: 15, color: MUTED });
    txt(s, "−" + num(drop(b)) + " pts", { x: 8.9, y: 4.8, w: 3.6, h: 0.8, fontSize: 40, bold: true, color: GREEN });
    txt(s, "ReLU6, sans SE : conçu pour l'int8", { x: 8.9, y: 5.7, w: 3.6, h: 0.4, fontSize: 13, color: MUTED });
  }

  // ===== 13. Quantization =====
  s = content("Quantization int8 : 4× plus léger", "MLOps");
  const qs = [["size_mb", "Taille du modèle (Mo)", "0.0"], ["latency_ms", "Latence par image (ms)", "0.0"], ["accuracy", "Accuracy test (%)", "0.0"]];
  qs.forEach(([k, title, fmt], i) => {
    const mult = k === "accuracy" ? 100 : 1;
    s.addChart(pres.charts.BAR, [{ name: title, labels: ["FP32", "INT8"], values: [+(b.fp32[k] * mult).toFixed(1), +(b.int8[k] * mult).toFixed(1)] }],
      chartBase({ x: 0.6 + i * 4.1, y: 1.4, w: 3.9, h: 4.2, barDir: "col", chartColors: [GREY, GREEN], invertedColors: [GREY, GREEN], barGapWidthPct: 50,
        showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: fmt, valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0,
        valAxisMaxVal: Math.max(b.fp32[k], b.int8[k]) * mult * 1.2, showTitle: true, title }));
  });
  // une couleur par barre
  const gain = (1 - b.int8.size_mb / b.fp32.size_mb), lat = (1 - b.int8.latency_ms / b.fp32.latency_ms), dAcc = (b.int8.accuracy - b.fp32.accuracy) * 100;
  txt(s, [
    { text: `−${Math.round(gain * 100)} % de taille`, options: { bold: true, color: GREEN } }, { text: "   ·   " },
    { text: `${lat >= 0 ? "−" : "+"}${Math.abs(Math.round(lat * 100))} % de latence`, options: { bold: true, color: GREEN } }, { text: "   ·   " },
    { text: `${dAcc >= 0 ? "+" : "−"}${num(Math.abs(dAcc))} point d'accuracy`, options: { bold: true, color: dAcc < -2 ? ORANGE : GREEN } }],
  { x: 0.6, y: 5.9, w: 12.1, h: 0.5, fontSize: 20, align: "center", color: MUTED });

  // ===== 14. Test de charge =====
  s = content("Test de charge avec Locust", "MLOps");
  const run3 = loadT["3"] || loadT["1"];
  if (loadT.timeline) {
    const tl = loadT.timeline;
    s.addChart(pres.charts.LINE, [{ name: "Requêtes / s", labels: tl.map((p) => String(p.t)), values: tl.map((p) => +p.rps.toFixed(1)) }],
      chartBase({ x: 0.6, y: 1.4, w: 7.6, h: 2.65, chartColors: [GREEN], lineSize: 2.5, lineDataSymbol: "none", showTitle: true, title: "Débit (requêtes / s)", catAxisLabelFrequency: 3 }));
    s.addChart(pres.charts.LINE, [{ name: "Utilisateurs", labels: tl.map((p) => String(p.t)), values: tl.map((p) => p.users) }],
      chartBase({ x: 0.6, y: 4.1, w: 7.6, h: 2.6, chartColors: [ORANGE], lineSize: 2.5, lineDataSymbol: "none", showTitle: true, title: "Utilisateurs simultanés", catAxisLabelFrequency: 3,
        showCatAxisTitle: true, catAxisTitle: "secondes", catAxisTitleColor: MUTED, catAxisTitleFontSize: 12 }));
  }
  if (run3) {
    s.addTable([tableHead(["Mesure", "Valeur"]),
      [{ text: "Requêtes envoyées" }, { text: String(run3.n), options: { bold: true } }],
      [{ text: "Débit moyen" }, { text: num(run3.rps) + " req/s", options: { bold: true } }],
      [{ text: "Latence médiane" }, { text: Math.round(run3.p50) + " ms", options: { bold: true } }],
      [{ text: "Latence p95" }, { text: Math.round(run3.p95) + " ms", options: { bold: true } }],
      [{ text: "Latence p99" }, { text: Math.round(run3.p99) + " ms", options: { bold: true } }],
      [{ text: "Erreurs" }, { text: String(run3.fail), options: { bold: true, color: run3.fail ? HEX.accent6 : GREEN } }]],
    { x: 8.6, y: 1.55, w: 4.15, colW: [2.3, 1.85], fontSize: 15, color: INK, rowH: 0.55, valign: "middle", border: { type: "solid", pt: 0.75, color: GRID } });
    txt(s, MEASURED, { x: 8.6, y: 5.6, w: 4.15, h: 0.35, fontSize: 11, color: MUTED, italic: true });
  }

  // ===== 15. Scaling =====
  s = content("Scaling horizontal : 1 API vs 3 API", "MLOps");
  if (loadT["1"] && loadT["3"]) {
    const r1 = loadT["1"], r3 = loadT["3"];
    s.addChart(pres.charts.BAR, [{ name: "Débit", labels: ["1 API", "3 API"], values: [+r1.rps.toFixed(1), +r3.rps.toFixed(1)] }],
      chartBase({ x: 0.6, y: 1.4, w: 4.6, h: 4.6, barDir: "col", chartColors: [GREY, GREEN], invertedColors: [GREY, GREEN], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
        valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: Math.max(r1.rps, r3.rps) * 1.2, showTitle: true, title: "Débit (req/s) — plus haut = mieux" }));
    s.addChart(pres.charts.BAR, [
      { name: "1 API", labels: ["Médiane", "p95"], values: [Math.round(r1.p50), Math.round(r1.p95)] },
      { name: "3 API", labels: ["Médiane", "p95"], values: [Math.round(r3.p50), Math.round(r3.p95)] }],
    chartBase({ x: 5.5, y: 1.4, w: 4.6, h: 4.6, barDir: "col", chartColors: [GREY, GREEN], showValue: true, dataLabelPosition: "outEnd", showLegend: true,
      valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: 0, valAxisMaxVal: Math.max(r1.p95, r3.p95) * 1.2, showTitle: true, title: "Latence (ms) — plus bas = mieux" }));
    card(s, 10.4, 1.6, 2.35, 4.3, TINT, "scale-card");
    stat(s, "×" + num(r3.rps / r1.rps), "de débit", 10.65, 1.85, 2.0, GREEN, 44);
    stat(s, "−" + Math.round((1 - r3.p50 / r1.p50) * 100) + " %", "de latence médiane", 10.65, 3.85, 2.0, GREEN, 44);
    txt(s, `Même charge : ${MEASURED}. Commande : docker compose up -d --scale api=3`, { x: 0.6, y: 6.25, w: 12, h: 0.4, fontSize: 12, color: MUTED, italic: true });
  }

  // ===== 16. Conclusion =====
  pres.addSection({ title: "Conclusion" });
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Conclusion" });
  txt(s, "En résumé", { x: 0.8, y: 0.6, w: 11, h: 0.9, fontSize: 40, bold: true, color: "FFFFFF" });
  const big = [[pct(b.int8.accuracy, 1), "accuracy en production"], [num(b.int8.size_mb) + " Mo", "modèle quantizé"], [run3 ? Math.round(run3.rps) + " req/s" : "–", "sous charge, 0 erreur"], ["7", "conteneurs, 1 commande"]];
  big.forEach(([v, l], i) => {
    const x = 0.8 + i * 3.05;
    txt(s, v, { x, y: 2.0, w: 2.9, h: 1.0, fontSize: 46, bold: true, color: MOSS });
    txt(s, l, { x, y: 3.05, w: 2.8, h: 0.5, fontSize: 16, color: HEX.accent5 });
  });
  txt(s, "Pistes", { x: 0.8, y: 4.4, w: 4, h: 0.5, fontSize: 22, bold: true, color: "FFFFFF" });
  const next = [[fa.FaCodeBranch, "Canary deployment"], [fa.FaDharmachakra, "Kubernetes"], [fa.FaRedo, "Ré-entraînement auto si drift"]];
  for (let i = 0; i < 3; i++) {
    const x = 0.8 + i * 4.1;
    await iconCircle(s, next[i][0], x, 5.15, 0.75, MOSS, HEX.dk2, "next-" + i);
    txt(s, next[i][1], { x: x + 0.95, y: 5.27, w: 3.0, h: 0.5, fontSize: 17, color: "FFFFFF" });
  }

  const out = path.join(__dirname, "TrashNet_MLOps.pptx");
  await pres.writeFile({ fileName: out });
  try { await require(process.env.APPLY_THEME).applyTheme(out, THEME); } catch { /* thème optionnel */ }
  console.log("OK ->", out);
})();
