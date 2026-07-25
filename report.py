"""
Generación del reporte HTML descargable.

Toma el DataFrame filtrado y arma un documento HTML autocontenido (sin
dependencias externas) con: resumen de limpieza, KPIs, insights de storytelling,
la tabla describe() del EDA y las tres gráficas analíticas incrustadas.
"""
from __future__ import annotations

import html
from datetime import datetime

import charts
import data_utils as du


def _bold(text: str) -> str:
    """Convierte el marcado **negrita** de los insights a <strong> seguro."""
    escaped = html.escape(text)
    while "**" in escaped:
        escaped = escaped.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
    return escaped


def _fmt_num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def build_report(df, filters: dict | None) -> str:
    """Devuelve el HTML completo del reporte como string."""
    k = du.kpis(df)
    ins = du.insights(df)
    desc = du.describe_table(df)
    figs = charts.build_all(df)
    clean = du.cleaning_report()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Descripción legible de los filtros activos.
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

    # Tabla describe().
    head = "".join(f"<th>{html.escape(c)}</th>" for c in desc["columns"])
    rows = ""
    for name, row in zip(desc["index"], desc["data"]):
        cells = "".join(f"<td>{v:,.2f}</td>" for v in row)
        rows += f"<tr><th>{html.escape(str(name))}</th>{cells}</tr>"

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
  h1 {{ font-size:30px; margin:0 0 4px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); font-size:14px; margin-bottom:6px; }}
  .filtro {{ display:inline-block; font-size:12.5px; color:var(--green);
             background:#e7f0e7; padding:5px 12px; border-radius:999px; margin:10px 0 28px; }}
  h2 {{ font-size:18px; margin:34px 0 14px; padding-bottom:8px;
        border-bottom:2px solid var(--green); }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
  .kpi {{ border:1px solid var(--line); border-radius:10px; padding:14px 16px;
          background:#fff; }}
  .kpi-val {{ display:block; font-size:22px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .kpi-lbl {{ display:block; font-size:12px; color:var(--muted); margin-top:2px; }}
  ul {{ padding-left:20px; }} li {{ margin:8px 0; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px;
           font-variant-numeric:tabular-nums; }}
  th,td {{ border:1px solid var(--line); padding:7px 10px; text-align:right; }}
  th:first-child, thead th {{ text-align:left; background:#f0f4ea; }}
  .fig {{ margin:16px 0; }} .fig img {{ max-width:100%; border:1px solid var(--line);
          border-radius:10px; }}
  .clean {{ font-size:13px; color:var(--muted); }}
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
  <div class="fig"><img src="{figs['heatmap']}" alt="Matriz de correlación"></div>
  <div class="fig"><img src="{figs['boxplot']}" alt="Producción por tecnificación"></div>
  <div class="fig"><img src="{figs['hist']}" alt="Distribución de rendimiento"></div>

  <h2>Calidad y preparación de datos</h2>
  <p class="clean">
    Dataset final: <strong>{clean['filas']} fincas</strong> ×
    {clean['columnas']} columnas · nulos restantes: {clean['nulos_restantes']} ·
    duplicados: {clean['duplicados']} ·
    columnas derivadas: {', '.join(clean['columnas_derivadas'])} ·
    auditorías entre {clean['rango_fechas'][0]} y {clean['rango_fechas'][1]}.
  </p>

  <footer>Dashboard AgroColombia · Fundamentos de Ciencias de Datos · Ejercicio 2</footer>
</div></body></html>"""
