/* =========================================================================
   AgroColombia — lógica del dashboard
   Maneja filtros, llama a la API, y pinta KPIs, gráficas Plotly, imágenes
   estáticas (Seaborn/Matplotlib), insights y la tabla del EDA.
   ========================================================================= */

// --- Sistema de color (coherente con el CSS y el skill de dataviz) --------- //
const INK = "#17251a", MUTED = "#6b7a63", GRID = "#e4e8dc", SURFACE = "#fbfcf8";
const GREEN = "#2e6b3e", GREEN_DEEP = "#16351f", GOLD = "#c88a2b";
// Paleta categórica validada (daltonismo) para los 5 cultivos.
const CAT = ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a"];
// Rampa ordinal verde para el nivel de tecnificación (Bajo -> Muy Alto).
const NIVEL_COLORS = ["#cfe3d0", "#7db487", "#3f7f4d", "#16351f"];

const FONT = { family: "IBM Plex Sans, system-ui, sans-serif", color: INK, size: 12 };
const PLOT_CONFIG = { displayModeBar: false, responsive: true };

// Mapa estable cultivo -> color (por orden alfabético, no por ranking).
let CROP_COLOR = {};

// Estado de los filtros.
const state = { departamentos: [], cultivos: [], niveles: [], riego: "todos" };

const $ = (id) => document.getElementById(id);
const loader = $("loader");

// ---------------- Utilidades de formato ---------------- //
const nf = new Intl.NumberFormat("es-CO");
function fmtInt(v) { return nf.format(Math.round(v)); }
function fmtCOP(v) {
  if (v >= 1e12) return (v / 1e12).toFixed(1) + " B";
  if (v >= 1e9)  return (v / 1e9).toFixed(1) + " mil M";
  if (v >= 1e6)  return (v / 1e6).toFixed(1) + " M";
  return fmtInt(v);
}

// ---------------- Arranque ---------------- //
async function init() {
  const res = await fetch("/api/meta");
  const { meta, cleaning } = await res.json();

  // Mapa de color estable por cultivo.
  meta.cultivos.forEach((c, i) => { CROP_COLOR[c] = CAT[i % CAT.length]; });

  buildChips("f-departamentos", meta.departamentos, "departamentos");
  buildChips("f-cultivos", meta.cultivos, "cultivos");
  buildChips("f-niveles", meta.niveles, "niveles");
  buildCleanStrip(cleaning);
  $("hero-count").textContent = cleaning.filas;

  // Segmentado de riego.
  $("f-riego").querySelectorAll("button").forEach((b) => {
    b.addEventListener("click", () => {
      $("f-riego").querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      state.riego = b.dataset.val;
      refresh();
    });
  });

  $("reset-btn").addEventListener("click", resetFilters);
  $("report-btn").addEventListener("click", downloadReport);

  refresh();
}

function buildChips(containerId, values, key) {
  const box = $(containerId);
  box.innerHTML = "";
  values.forEach((v) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = v;
    chip.addEventListener("click", () => {
      chip.classList.toggle("on");
      const arr = state[key];
      const i = arr.indexOf(v);
      if (i >= 0) arr.splice(i, 1); else arr.push(v);
      refresh();
    });
    box.appendChild(chip);
  });
}

function buildCleanStrip(c) {
  $("clean-strip").innerHTML = [
    `<b>${c.filas}</b> fincas`,
    `<b>${c.columnas}</b> variables`,
    `<b>${c.nulos_restantes}</b> nulos`,
    `<b>${c.duplicados}</b> duplicados`,
    `+2 columnas derivadas`,
    `auditorías ${c.rango_fechas[0]} → ${c.rango_fechas[1]}`,
  ].map((t) => `<span class="clean-pill">${t}</span>`).join("");
}

function resetFilters() {
  state.departamentos = []; state.cultivos = []; state.niveles = []; state.riego = "todos";
  document.querySelectorAll(".chip.on").forEach((c) => c.classList.remove("on"));
  $("f-riego").querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.val === "todos"));
  refresh();
}

// ---------------- Ciclo de actualización ---------------- //
let pending = null;
function refresh() {
  clearTimeout(pending);
  pending = setTimeout(fetchAndRender, 120); // debounce ligero
}

async function fetchAndRender() {
  loader.classList.remove("hidden");
  try {
    const res = await fetch("/api/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    const d = await res.json();
    renderKPIs(d.kpis);
    renderPlots(d.charts);
    if (d.static_charts) renderStatic(d.static_charts);      // local: imágenes MPL
    else if (d.analytic_data) renderAnalytic(d.analytic_data); // vercel: Plotly.js
    renderInsights(d.insights);
    renderTable(d.describe);
  } catch (e) {
    console.error(e);
  } finally {
    loader.classList.add("hidden");
  }
}

// ---------------- KPIs ---------------- //
function renderKPIs(k) {
  const cards = [
    { val: fmtInt(k.n_fincas), unit: "", lbl: "Fincas", cls: "" },
    { val: fmtInt(k.area_total), unit: " ha", lbl: "Área total", cls: "" },
    { val: fmtInt(k.produccion_total), unit: " Ton", lbl: "Producción anual", cls: "" },
    { val: "$" + fmtInt(k.precio_promedio), unit: "", lbl: "Precio medio / Ton", cls: "accent-gold" },
    { val: k.rendimiento_promedio.toFixed(1), unit: " Ton/ha", lbl: "Rendimiento medio", cls: "" },
    { val: "$" + fmtCOP(k.ingreso_total), unit: " COP", lbl: "Ingreso estimado", cls: "accent-clay" },
  ];
  $("kpi-strip").innerHTML = cards.map((c) => `
    <div class="kpi ${c.cls}">
      <span class="val">${c.val}<span class="unit">${c.unit}</span></span>
      <span class="lbl">${c.lbl}</span>
    </div>`).join("");
}

// ---------------- Gráficas Plotly ---------------- //
const baseLayout = (extra = {}) => Object.assign({
  font: FONT,
  paper_bgcolor: SURFACE,
  plot_bgcolor: SURFACE,
  margin: { l: 60, r: 18, t: 10, b: 44 },
  xaxis: { gridcolor: GRID, zeroline: false, linecolor: GRID },
  yaxis: { gridcolor: GRID, zeroline: false, linecolor: GRID },
  hoverlabel: { bgcolor: INK, font: { color: "#fff", family: FONT.family } },
}, extra);

function renderPlots(c) {
  // --- Producción por departamento (barras horizontales, verde) ---
  Plotly.react("plot-dept", [{
    type: "bar", orientation: "h",
    x: c.prod_dept.values, y: c.prod_dept.labels,
    marker: { color: GREEN, line: { width: 0 } },
    hovertemplate: "%{y}<br>%{x:,.0f} Ton<extra></extra>",
  }], baseLayout({
    margin: { l: 120, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: GRID, zeroline: false, title: { text: "Producción (Ton)", font: { size: 11, color: MUTED } } },
    yaxis: { gridcolor: "rgba(0,0,0,0)", automargin: true },
  }), PLOT_CONFIG);

  // --- Precio promedio por cultivo (barras, color = cultivo) ---
  Plotly.react("plot-precio", [{
    type: "bar",
    x: c.precio_cultivo.labels, y: c.precio_cultivo.values,
    marker: { color: c.precio_cultivo.labels.map((l) => CROP_COLOR[l] || GREEN) },
    hovertemplate: "%{x}<br>$%{y:,.0f} COP/Ton<extra></extra>",
  }], baseLayout({
    margin: { l: 68, r: 18, t: 10, b: 70 },
    xaxis: { gridcolor: "rgba(0,0,0,0)", tickangle: -18, automargin: true },
    yaxis: { gridcolor: GRID, title: { text: "COP / Ton", font: { size: 11, color: MUTED } } },
  }), PLOT_CONFIG);

  // --- Dispersión Área vs Producción por cultivo ---
  const traces = Object.entries(c.scatter.cultivos).map(([cultivo, s]) => ({
    type: "scatter", mode: "markers", name: cultivo,
    x: s.x, y: s.y,
    customdata: s.rinde,
    marker: { color: CROP_COLOR[cultivo] || GREEN, size: 9, opacity: 0.8,
              line: { color: SURFACE, width: 1 } },
    hovertemplate: `<b>${cultivo}</b><br>Área %{x} ha<br>Producción %{y} Ton<br>Rinde %{customdata} Ton/ha<extra></extra>`,
  }));
  Plotly.react("plot-scatter", traces, baseLayout({
    margin: { l: 58, r: 18, t: 10, b: 46 },
    legend: { orientation: "h", y: -0.18, font: { size: 11 } },
    xaxis: { gridcolor: GRID, title: { text: "Área (ha)", font: { size: 11, color: MUTED } } },
    yaxis: { gridcolor: GRID, title: { text: "Producción (Ton)", font: { size: 11, color: MUTED } } },
  }), PLOT_CONFIG);

  // --- Dona: nivel de tecnificación (rampa ordinal verde) ---
  Plotly.react("plot-tech", [{
    type: "pie", hole: 0.58,
    labels: c.tech_dist.labels, values: c.tech_dist.values,
    marker: { colors: NIVEL_COLORS, line: { color: SURFACE, width: 2 } },
    sort: false, direction: "clockwise",
    textfont: { color: INK, family: FONT.family, size: 12 },
    hovertemplate: "%{label}<br>%{value} fincas (%{percent})<extra></extra>",
  }], baseLayout({
    margin: { l: 10, r: 10, t: 10, b: 10 },
    showlegend: true,
    legend: { orientation: "h", y: -0.05, font: { size: 11 } },
  }), PLOT_CONFIG);

  updateStories(c);
}

function updateStories(c) {
  // Departamento líder.
  if (c.prod_dept.values.length) {
    const i = c.prod_dept.values.indexOf(Math.max(...c.prod_dept.values));
    $("story-dept").innerHTML =
      `Lidera <strong>${c.prod_dept.labels[i]}</strong> con ${fmtInt(c.prod_dept.values[i])} Ton.`;
  } else { $("story-dept").textContent = "Sin datos."; }

  // Cultivo mejor pagado.
  if (c.precio_cultivo.values.length) {
    $("story-precio").innerHTML =
      `El más caro: <strong>${c.precio_cultivo.labels[0]}</strong> ($${fmtInt(c.precio_cultivo.values[0])}/Ton).`;
  } else { $("story-precio").textContent = "Sin datos."; }

  // Scatter.
  const nCult = Object.keys(c.scatter.cultivos).length;
  $("story-scatter").innerHTML =
    `Cada punto es una finca; el color indica el cultivo (${nCult} tipos). Busca si más área implica más producción.`;

  // Tecnificación dominante.
  if (c.tech_dist.values.length) {
    const i = c.tech_dist.values.indexOf(Math.max(...c.tech_dist.values));
    $("story-tech").innerHTML =
      `Predomina el nivel <strong>${c.tech_dist.labels[i]}</strong> (${c.tech_dist.values[i]} fincas).`;
  }
}

// ---------------- Gráficas analíticas ---------------- //
// Modo local: PNG de Matplotlib/Seaborn incrustado como imagen.
function renderStatic(s) {
  const imgs = { "slot-heatmap": s.heatmap, "slot-boxplot": s.boxplot, "slot-hist": s.hist };
  for (const [id, src] of Object.entries(imgs)) {
    $(id).innerHTML = `<img class="static-img" src="${src}" alt="">`;
  }
}

// Modo Vercel: las mismas 3 gráficas dibujadas con Plotly.js en el cliente.
function renderAnalytic(a) {
  // 1) Heatmap de correlación (divergente).
  Plotly.react("slot-heatmap", [{
    type: "heatmap", z: a.corr.z, x: a.corr.labels, y: a.corr.labels,
    colorscale: [[0, "#2a78d6"], [0.5, "#eef1ea"], [1, "#e34948"]],
    zmid: 0, zmin: -1, zmax: 1,
    text: a.corr.z, texttemplate: "%{text:.2f}",
    textfont: { size: 11, color: INK },
    hovertemplate: "%{y} · %{x}<br>r = %{z:.2f}<extra></extra>",
    colorbar: { title: "r", thickness: 12, len: 0.9 },
  }], baseLayout({
    margin: { l: 90, r: 20, t: 10, b: 70 }, height: 320,
    xaxis: { tickangle: -25, gridcolor: "rgba(0,0,0,0)" },
    yaxis: { gridcolor: "rgba(0,0,0,0)", autorange: "reversed" },
  }), PLOT_CONFIG);

  // 2) Boxplot de producción por nivel de tecnificación (rampa verde).
  const boxTraces = a.box.levels.map((lvl) => ({
    type: "box", name: lvl, y: a.box.values[lvl],
    marker: { color: NIVEL_COLORS[["Bajo", "Medio", "Alto", "Muy Alto"].indexOf(lvl)] },
    boxpoints: "outliers", line: { width: 1.4 },
  }));
  Plotly.react("slot-boxplot", boxTraces, baseLayout({
    margin: { l: 54, r: 16, t: 10, b: 36 }, height: 320, showlegend: false,
    yaxis: { gridcolor: GRID, title: { text: "Producción (Ton)", font: { size: 11, color: MUTED } } },
    xaxis: { gridcolor: "rgba(0,0,0,0)" },
  }), PLOT_CONFIG);

  // 3) Histograma del rendimiento con línea de media.
  Plotly.react("slot-hist", [{
    type: "histogram", x: a.hist.values, nbinsx: 24,
    marker: { color: GREEN, line: { color: SURFACE, width: 1 } },
    hovertemplate: "%{x} Ton/ha<br>%{y} fincas<extra></extra>",
  }], baseLayout({
    margin: { l: 48, r: 16, t: 10, b: 40 }, height: 320,
    xaxis: { gridcolor: GRID, title: { text: "Rendimiento (Ton/ha)", font: { size: 11, color: MUTED } } },
    yaxis: { gridcolor: GRID, title: { text: "Nº de fincas", font: { size: 11, color: MUTED } } },
    shapes: [{ type: "line", x0: a.hist.mean, x1: a.hist.mean, yref: "paper", y0: 0, y1: 1,
               line: { color: "#a5352a", width: 1.8, dash: "dash" } }],
    annotations: [{ x: a.hist.mean, yref: "paper", y: 0.96, text: `media ${a.hist.mean}`,
                    showarrow: false, xanchor: "left", font: { color: "#a5352a", size: 11 } }],
  }), PLOT_CONFIG);
}

// ---------------- Insights ---------------- //
function renderInsights(list) {
  $("insights-list").innerHTML = list
    .map((t) => `<li>${boldMd(t)}</li>`).join("");
}
function boldMd(t) {
  return t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// ---------------- Tabla describe() ---------------- //
function renderTable(d) {
  if (!d.columns.length) { $("describe-table").innerHTML = ""; return; }
  const head = `<thead><tr><th></th>${d.columns.map((c) => `<th>${c}</th>`).join("")}</tr></thead>`;
  const body = d.index.map((name, r) =>
    `<tr><th>${name}</th>${d.data[r].map((v) =>
      `<td>${nf.format(Number(v.toFixed(2)))}</td>`).join("")}</tr>`).join("");
  $("describe-table").innerHTML = head + `<tbody>${body}</tbody>`;
}

// ---------------- Reporte ---------------- //
async function downloadReport() {
  const btn = $("report-btn");
  btn.disabled = true; btn.textContent = "Generando…";
  try {
    const res = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "reporte_agrocolombia.html";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  } finally {
    btn.disabled = false; btn.textContent = "Descargar reporte HTML";
  }
}

init();
