"""
Dashboard AgroColombia — servidor Flask.

Funciona en dos modos, según las librerías disponibles:
  - LOCAL  (con Matplotlib/Seaborn): las 3 gráficas analíticas se generan en el
    servidor como PNG (cumple el requisito de usar Seaborn + Matplotlib + Plotly).
  - VERCEL (sin Matplotlib/Seaborn): esas gráficas se envían como datos crudos y
    se dibujan con Plotly.js en el cliente, para que el backend solo dependa de
    pandas/numpy y quepa en el límite de las funciones serverless.

Rutas:
  GET  /               -> página del dashboard
  GET  /api/meta       -> opciones de filtros + resumen de limpieza
  POST /api/data       -> KPIs, series Plotly, gráficas/insights, tabla
  POST /api/report     -> reporte HTML descargable

Ejecutar en local:  python app.py   (http://127.0.0.1:5000)
"""
from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request, Response

import data_utils as du

# Detección de Matplotlib/Seaborn: define en qué modo corremos.
# AGRO_LIGHT=1 fuerza el modo ligero (Plotly) para probar el camino de Vercel
# en local sin desinstalar Matplotlib.
if os.environ.get("AGRO_LIGHT") == "1":
    HAS_MPL = False
    import report_web
else:
    try:
        import charts        # matplotlib + seaborn
        import report        # reporte con imágenes PNG
        HAS_MPL = True
    except Exception:        # noqa: BLE001 - en Vercel no están instaladas
        HAS_MPL = False
        import report_web    # reporte con Plotly (ligero)

# Rutas absolutas para que las plantillas/estáticos se resuelvan también en
# entornos serverless donde el working dir puede diferir.
_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_HERE, "templates"),
    static_folder=os.path.join(_HERE, "static"),
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/meta")
def api_meta():
    return jsonify({"meta": du.meta(), "cleaning": du.cleaning_report()})


@app.route("/api/data", methods=["POST"])
def api_data():
    filters = request.get_json(silent=True) or {}
    df = du.apply_filters(filters)
    payload = {
        "kpis": du.kpis(df),
        "charts": du.chart_data(df),
        "insights": du.insights(df),
        "describe": du.describe_table(df),
    }
    if HAS_MPL:
        payload["static_charts"] = charts.build_all(df)   # PNGs Seaborn/MPL
    else:
        payload["analytic_data"] = du.analytic_data(df)   # datos para Plotly.js
    return jsonify(payload)


@app.route("/api/report", methods=["POST"])
def api_report():
    filters = request.get_json(silent=True) or {}
    df = du.apply_filters(filters)
    builder = report.build_report if HAS_MPL else report_web.build_report
    html_doc = builder(df, filters)
    return Response(
        html_doc,
        mimetype="text/html",
        headers={
            "Content-Disposition": "attachment; filename=reporte_agrocolombia.html"
        },
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
