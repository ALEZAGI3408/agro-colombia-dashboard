"""
Reporte HTML descargable — versión ligera (modo Vercel).

Idéntico en estructura a report.py, pero las gráficas se construyen con
plotly (Python puro, sin Matplotlib/Seaborn/SciPy) y se incrustan como HTML
interactivo. Se usa cuando Matplotlib no está disponible.
"""
from __future__ import annotations

import html
from datetime import datetime

import plotly.graph_objects as go

import data_utils as du

GREEN = "#2e6b3e"
NIVEL_COLORS = ["#cfe3d0", "#7db487", "#3f7f4d", "#16351f"]
DIVERGING = [[0, "#2a78d6"], [0.5, "#eef1ea"], [1, "#e34948"]]
SURFACE = "#fbfcf8"
INK = "#17251a"


def _bold(text: str) -> str:
    escaped = html.escape(text)
    while "**" in escaped:
        escaped = escaped.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
    return escaped


def _fmt_num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _base_layout(**extra):
    layout = dict(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="IBM Plex Sans, sans-serif", color=INK, size=12),
        margin=dict(l=60, r=20, t=40, b=50), height=380,
    )
    layout.update(extra)
    return layout


def _figures(df) -> list[str]:
    """Devuelve los <div> HTML de las 3 gráficas analíticas."""
    ad = du.analytic_data(df)
    htmls = []

    # 1) Heatmap de correlación.
    fig = go.Figure(go.Heatmap(
        z=ad["corr"]["z"], x=ad["corr"]["labels"], y=ad["corr"]["labels"],
        colorscale=DIVERGING, zmid=0, zmin=-1, zmax=1,
        text=ad["corr"]["z"], texttemplate="%{text:.2f}",
        colorbar=dict(title="r"),
    ))
    fig.update_layout(**_base_layout(title="Correlación entre variables"))

    # 2) Boxplot producción por tecnificación.
    fig2 = go.Figure()
    for i, lvl in enumerate(ad["box"]["levels"]):
        fig2.add_trace(go.Box(
            y=ad["box"]["values"][lvl], name=lvl,
            marker_color=NIVEL_COLORS[du.NIVEL_ORDEN.index(lvl)],
            boxpoints="outliers",
        ))
    fig2.update_layout(**_base_layout(
        title="Producción anual por nivel de tecnificación",
        showlegend=False, yaxis_title="Producción (Ton)"))

    # 3) Histograma de rendimiento.
    fig3 = go.Figure(go.Histogram(
        x=ad["hist"]["values"], nbinsx=24, marker_color=GREEN,
        marker_line_color=SURFACE, marker_line_width=1,
    ))
    fig3.add_vline(x=ad["hist"]["mean"], line_dash="dash", line_color="#a5352a",
                   annotation_text=f"media {ad['hist']['mean']}")
    fig3.update_layout(**_base_layout(
        title="Distribución del rendimiento (Ton/ha)",
        xaxis_title="Rendimiento (Ton/ha)", yaxis_title="Nº de fincas"))

    for i, f in enumerate([fig, fig2, fig3]):
        htmls.append(f.to_html(
            full_html=False,
            include_plotlyjs="cdn" if i == 0 else False,
            config={"displayModeBar": False},
        ))
    return htmls


def build_report(df, filters: dict | None) -> str:
    k = du.kpis(df)
    ins = du.insights(df)
    desc = du.describe_table(df)
    clean = du.cleaning_report()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    filters = filters or {}
    partes = []
    if filters.get("departamentos"):
        partes.append("Departamentos: " + ", ".join(filters["departamentos"]))
    if filters.get("cultivos"):
        partes.append("Cultivos: " + ", ".join(filters["cultivos"]))
    if filters.get("niveles"):
        partes.append("Tecnificación: " + ", ".join(filters["niveles"]))
    riego = filters.get("riego", "todos")
    if riego != "todos":
        partes.append("Riego tecnificado: " + ("Sí" if riego == "si" else "No"))
    filtro_txt = " · ".join(partes) if partes else "Sin filtros (dataset completo)"

    kpi_cards = "".join(
        f'<div class="kpi"><span class="kpi-val">{val}</span>'
        f'<span class="kpi-lbl">{lbl}</span></div>'
        for lbl, val in [
            ("Fincas", _fmt_num(k["n_fincas"])),
            ("Área total (ha)", _fmt_num(k["area_total"])),
            ("Producción (Ton)", _fmt_num(k["produccion_total"])),
            ("Precio medio (COP/Ton)", _fmt_num(k["precio_promedio"])),
            ("Rendimiento medio (Ton/ha)", f'{k["rendimiento_promedio"]:.1f}'),
            ("Ingreso estimado (COP)", _fmt_num(k["ingreso_total"])),
        ]
    )
    insights_html = "".join(f"<li>{_bold(t)}</li>" for t in ins)
    head = "".join(f"<th>{html.escape(c)}</th>" for c in desc["columns"])
    rows = ""
    for name, row in zip(desc["index"], desc["data"]):
        cells = "".join(f"<td>{v:,.2f}</td>" for v in row)
        rows += f"<tr><th>{html.escape(str(name))}</th>{cells}</tr>"

    figs = _figures(df)

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Reporte AgroColombia — {now}</title>
<style>
  :root {{ --green:#2e6b3e; --ink:#17251a; --muted:#6b7a63; --line:rgba(23,37,26,.12); }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--ink);
         background:#eef1e6; margin:0; padding:40px 32px; line-height:1.5; }}
  .wrap {{ max-width:900px; margin:0 auto; background:#fbfcf8; padding:44px 48px;
           border:1px solid var(--line); border-radius:14px; }}
  h1 {{ font-size:30px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:14px; }}
  .filtro {{ display:inline-block; font-size:12.5px; color:var(--green);
             background:#e7f0e7; padding:5px 12px; border-radius:999px; margin:10px 0 28px; }}
  h2 {{ font-size:18px; margin:34px 0 14px; padding-bottom:8px; border-bottom:2px solid var(--green); }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
  .kpi {{ border:1px solid var(--line); border-radius:10px; padding:14px 16px; background:#fff; }}
  .kpi-val {{ display:block; font-size:22px; font-weight:700; }}
  .kpi-lbl {{ display:block; font-size:12px; color:var(--muted); margin-top:2px; }}
  ul {{ padding-left:20px; }} li {{ margin:8px 0; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; }}
  th,td {{ border:1px solid var(--line); padding:7px 10px; text-align:right; }}
  thead th {{ text-align:left; background:#f0f4ea; }}
  .fig {{ margin:16px 0; }}
  footer {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); }}
</style></head>
<body><div class="wrap">
  <h1>Reporte AgroColombia</h1>
  <div class="sub">Análisis exploratorio de fincas agrícolas colombianas · generado {now}</div>
  <span class="filtro">{html.escape(filtro_txt)}</span>

  <h2>Indicadores clave</h2>
  <div class="kpis">{kpi_cards}</div>

  <h2>Hallazgos (storytelling)</h2>
  <ul>{insights_html}</ul>

  <h2>Estadística descriptiva</h2>
  <table><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table>

  <h2>Gráficas analíticas</h2>
  <div class="fig">{figs[0]}</div>
  <div class="fig">{figs[1]}</div>
  <div class="fig">{figs[2]}</div>

  <h2>Calidad y preparación de datos</h2>
  <p class="sub">Dataset final: <strong>{clean['filas']} fincas</strong> ×
    {clean['columnas']} columnas · nulos: {clean['nulos_restantes']} ·
    duplicados: {clean['duplicados']} · columnas derivadas:
    {', '.join(clean['columnas_derivadas'])}.</p>

  <footer>Dashboard AgroColombia · Fundamentos de Ciencias de Datos · Ejercicio 2</footer>
</div></body></html>"""
