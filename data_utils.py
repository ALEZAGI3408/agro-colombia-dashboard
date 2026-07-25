"""
Capa de datos del dashboard AgroColombia.

Responsabilidades:
  - Cargar el CSV una sola vez.
  - Limpiar / imputar / derivar columnas (dejar el dataset "correcto").
  - Filtrar según las selecciones del usuario.
  - Producir las agregaciones y los insights narrativos del EDA.

El resto de la app (Flask, gráficas, reporte) consume estas funciones y nunca
toca el CSV directamente.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(__file__)
# En local existe el CSV; en el despliegue (Vercel) se envía comprimido (.gz)
# para reducir tamaño. pandas lee ambos formatos de forma transparente.
_CSV = os.path.join(_HERE, "agro_colombia.csv")
CSV_PATH = _CSV if os.path.exists(_CSV) else _CSV + ".gz"

# Orden natural del nivel de tecnificación (ordinal, no alfabético).
NIVEL_ORDEN = ["Bajo", "Medio", "Alto", "Muy Alto"]

# Etiquetas legibles para las columnas numéricas (usadas en tooltips/reporte).
NUM_LABELS = {
    "Area_Hectareas": "Área (ha)",
    "Produccion_Anual_Ton": "Producción (Ton)",
    "Precio_Venta_Por_Ton_COP": "Precio (COP/Ton)",
    "Rendimiento_Ton_Ha": "Rendimiento (Ton/ha)",
    "Ingreso_Estimado_COP": "Ingreso estimado (COP)",
}


def load_data() -> pd.DataFrame:
    """Carga y limpia el dataset. Se invoca una vez al arrancar la app."""
    df = pd.read_csv(CSV_PATH, encoding="utf-8")

    # --- Tipos ---------------------------------------------------------------
    # Fecha de auditoría -> datetime real (venía como texto).
    df["Fecha_Ultima_Auditoria"] = pd.to_datetime(
        df["Fecha_Ultima_Auditoria"], errors="coerce"
    )

    # Nivel de tecnificación como categórica ordenada (Bajo < ... < Muy Alto).
    df["Nivel_Tecnificacion"] = pd.Categorical(
        df["Nivel_Tecnificacion"].str.strip(),
        categories=NIVEL_ORDEN,
        ordered=True,
    )

    # Normalizar espacios en las columnas de texto.
    for col in ["Departamento", "Tipo_Cultivo", "Tipo_Suelo"]:
        df[col] = df[col].astype(str).str.strip()

    # --- Imputación / saneamiento numérico -----------------------------------
    # Aunque el dataset viene sin nulos, dejamos la red de seguridad: cualquier
    # valor no positivo en área o producción se trata como faltante y se imputa
    # con la mediana del mismo tipo de cultivo (imputación por grupo).
    for col in ["Area_Hectareas", "Produccion_Anual_Ton", "Precio_Venta_Por_Ton_COP"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] <= 0, col] = np.nan
        df[col] = df.groupby("Tipo_Cultivo")[col].transform(
            lambda s: s.fillna(s.median())
        )

    # Eliminar filas duplicadas exactas y por ID de finca (integridad).
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset="ID_Finca", keep="first")

    # --- Columnas derivadas (valor del negocio) ------------------------------
    # Rendimiento: producción por hectárea (indicador de productividad).
    df["Rendimiento_Ton_Ha"] = df["Produccion_Anual_Ton"] / df["Area_Hectareas"]
    # Ingreso estimado anual = producción * precio por tonelada.
    df["Ingreso_Estimado_COP"] = (
        df["Produccion_Anual_Ton"] * df["Precio_Venta_Por_Ton_COP"]
    )

    return df.reset_index(drop=True)


# El dataset se carga una sola vez a nivel de módulo.
DF = load_data()


def cleaning_report() -> dict:
    """Resumen de la limpieza aplicada, para mostrar en el dashboard/reporte."""
    return {
        "filas": int(DF.shape[0]),
        "columnas": int(DF.shape[1]),
        "nulos_restantes": int(DF.isnull().sum().sum()),
        "duplicados": int(DF.duplicated().sum()),
        "columnas_derivadas": ["Rendimiento_Ton_Ha", "Ingreso_Estimado_COP"],
        "rango_fechas": [
            DF["Fecha_Ultima_Auditoria"].min().strftime("%Y-%m-%d"),
            DF["Fecha_Ultima_Auditoria"].max().strftime("%Y-%m-%d"),
        ],
    }


def meta() -> dict:
    """Opciones para poblar los filtros del frontend."""
    return {
        "departamentos": sorted(DF["Departamento"].unique().tolist()),
        "cultivos": sorted(DF["Tipo_Cultivo"].unique().tolist()),
        "niveles": NIVEL_ORDEN,
    }


def apply_filters(filters: dict | None) -> pd.DataFrame:
    """Devuelve un sub-DataFrame según los filtros del usuario.

    filters admite las claves: departamentos[], cultivos[], niveles[], riego
    ('todos' | 'si' | 'no'). Listas vacías = sin filtrar por esa dimensión.
    """
    filters = filters or {}
    df = DF

    deps = filters.get("departamentos") or []
    if deps:
        df = df[df["Departamento"].isin(deps)]

    cultivos = filters.get("cultivos") or []
    if cultivos:
        df = df[df["Tipo_Cultivo"].isin(cultivos)]

    niveles = filters.get("niveles") or []
    if niveles:
        df = df[df["Nivel_Tecnificacion"].isin(niveles)]

    riego = filters.get("riego", "todos")
    if riego == "si":
        df = df[df["Sistema_Riego_Tecnificado"] == True]  # noqa: E712
    elif riego == "no":
        df = df[df["Sistema_Riego_Tecnificado"] == False]  # noqa: E712

    return df


# --------------------------------------------------------------------------- #
# Agregaciones para las gráficas interactivas (Plotly).                        #
# --------------------------------------------------------------------------- #
def kpis(df: pd.DataFrame) -> dict:
    """Indicadores clave, reactivos a los filtros."""
    if df.empty:
        return {
            "n_fincas": 0, "area_total": 0, "produccion_total": 0,
            "precio_promedio": 0, "rendimiento_promedio": 0, "ingreso_total": 0,
        }
    return {
        "n_fincas": int(df.shape[0]),
        "area_total": float(df["Area_Hectareas"].sum()),
        "produccion_total": float(df["Produccion_Anual_Ton"].sum()),
        "precio_promedio": float(df["Precio_Venta_Por_Ton_COP"].mean()),
        "rendimiento_promedio": float(df["Rendimiento_Ton_Ha"].mean()),
        "ingreso_total": float(df["Ingreso_Estimado_COP"].sum()),
    }


def chart_data(df: pd.DataFrame) -> dict:
    """Series listas para las gráficas Plotly del frontend."""
    if df.empty:
        return {"prod_dept": {"labels": [], "values": []},
                "scatter": {"cultivos": {}},
                "precio_cultivo": {"labels": [], "values": []},
                "tech_dist": {"labels": [], "values": []}}

    # Producción total por departamento (barras, magnitud).
    g = (df.groupby("Departamento")["Produccion_Anual_Ton"].sum()
           .sort_values(ascending=True))
    prod_dept = {"labels": g.index.tolist(), "values": [round(v, 1) for v in g.values]}

    # Dispersión Área vs Producción, separada por cultivo (identidad).
    scatter = {"cultivos": {}}
    for cultivo, sub in df.groupby("Tipo_Cultivo"):
        scatter["cultivos"][cultivo] = {
            "x": [round(v, 2) for v in sub["Area_Hectareas"].tolist()],
            "y": [round(v, 1) for v in sub["Produccion_Anual_Ton"].tolist()],
            "rinde": [round(v, 2) for v in sub["Rendimiento_Ton_Ha"].tolist()],
        }

    # Precio promedio por cultivo (barras, misma identidad de color).
    p = (df.groupby("Tipo_Cultivo")["Precio_Venta_Por_Ton_COP"].mean()
           .sort_values(ascending=False))
    precio_cultivo = {"labels": p.index.tolist(),
                      "values": [round(v) for v in p.values]}

    # Distribución de nivel de tecnificación (dona, ordinal).
    t = df["Nivel_Tecnificacion"].value_counts().reindex(NIVEL_ORDEN).fillna(0)
    tech_dist = {"labels": NIVEL_ORDEN, "values": [int(v) for v in t.values]}

    return {"prod_dept": prod_dept, "scatter": scatter,
            "precio_cultivo": precio_cultivo, "tech_dist": tech_dist}


def _fmt_cop(v: float) -> str:
    """Formatea pesos colombianos de forma compacta."""
    if v >= 1e12:
        return f"${v/1e12:.1f} billones COP"
    if v >= 1e9:
        return f"${v/1e9:.1f} mil millones COP"
    if v >= 1e6:
        return f"${v/1e6:.1f} millones COP"
    return f"${v:,.0f} COP"


def insights(df: pd.DataFrame) -> list[str]:
    """Narrativa de storytelling generada a partir de los datos filtrados."""
    if df.empty:
        return ["No hay fincas que cumplan los filtros seleccionados."]

    out = []

    # Departamento líder en producción.
    g = df.groupby("Departamento")["Produccion_Anual_Ton"].sum()
    top_dep = g.idxmax()
    share = g.max() / g.sum() * 100
    out.append(
        f"**{top_dep}** concentra la mayor producción "
        f"({g.max():,.0f} Ton, {share:.0f}% del total filtrado)."
    )

    # Cultivo mejor pagado.
    p = df.groupby("Tipo_Cultivo")["Precio_Venta_Por_Ton_COP"].mean()
    top_crop = p.idxmax()
    out.append(
        f"El cultivo mejor pagado es **{top_crop}**, con un precio promedio de "
        f"{_fmt_cop(p.max())} por tonelada."
    )

    # Relación área–producción.
    if df.shape[0] > 2:
        corr = df["Area_Hectareas"].corr(df["Produccion_Anual_Ton"])
        fuerza = ("fuerte" if abs(corr) >= 0.6 else
                  "moderada" if abs(corr) >= 0.3 else "débil")
        signo = "positiva" if corr >= 0 else "negativa"
        out.append(
            f"La correlación entre área y producción es {fuerza} y {signo} "
            f"(r = {corr:.2f}): más hectáreas no garantizan más toneladas."
        )

    # Efecto de la tecnificación en el rendimiento.
    r = df.groupby("Nivel_Tecnificacion", observed=True)["Rendimiento_Ton_Ha"].mean()
    if r.notna().sum() >= 2:
        best = r.idxmax()
        out.append(
            f"Las fincas con tecnificación **{best}** logran el mayor rendimiento "
            f"promedio ({r.max():.1f} Ton/ha)."
        )

    # Cobertura de riego tecnificado.
    pct_riego = df["Sistema_Riego_Tecnificado"].mean() * 100
    out.append(
        f"El **{pct_riego:.0f}%** de las fincas filtradas cuenta con riego "
        f"tecnificado."
    )

    # Ingreso estimado agregado.
    out.append(
        f"El ingreso anual estimado del conjunto es **{_fmt_cop(df['Ingreso_Estimado_COP'].sum())}**."
    )

    return out


def describe_table(df: pd.DataFrame) -> dict:
    """Tabla describe() de las variables numéricas, para el EDA/reporte."""
    cols = list(NUM_LABELS.keys())
    if df.empty:
        return {"columns": [], "index": [], "data": []}
    desc = df[cols].describe().round(2)
    return {
        "columns": [NUM_LABELS[c] for c in desc.columns],
        "index": desc.index.tolist(),
        "data": desc.values.tolist(),
    }


# --------------------------------------------------------------------------- #
# Datos crudos para renderizar las gráficas analíticas en el cliente (Plotly). #
# Se usa cuando Matplotlib/Seaborn no están disponibles (p.ej. en Vercel), de  #
# modo que el backend solo dependa de pandas/numpy y quepa en serverless.      #
# --------------------------------------------------------------------------- #
def analytic_data(df: pd.DataFrame) -> dict:
    """Correlación, boxplot por tecnificación e histograma de rendimiento."""
    cols = ["Area_Hectareas", "Produccion_Anual_Ton",
            "Precio_Venta_Por_Ton_COP", "Rendimiento_Ton_Ha",
            "Ingreso_Estimado_COP"]
    labels = ["Área", "Producción", "Precio", "Rendimiento", "Ingreso"]

    if df.shape[0] < 3:
        return {"corr": {"labels": labels, "z": []},
                "box": {"levels": [], "values": {}},
                "hist": {"values": [], "mean": 0}}

    # Matriz de correlación.
    corr = df[cols].corr().round(2)
    corr_z = [[None if pd.isna(v) else float(v) for v in row]
              for row in corr.values]

    # Producción por nivel de tecnificación (valores crudos -> Plotly box).
    niveles = [n for n in NIVEL_ORDEN if (df["Nivel_Tecnificacion"] == n).any()]
    values = {
        n: [round(v, 1) for v in
            df.loc[df["Nivel_Tecnificacion"] == n, "Produccion_Anual_Ton"].tolist()]
        for n in niveles
    }

    # Rendimiento (valores crudos -> Plotly histogram).
    rinde = [round(v, 2) for v in df["Rendimiento_Ton_Ha"].tolist()]

    return {
        "corr": {"labels": labels, "z": corr_z},
        "box": {"levels": niveles, "values": values},
        "hist": {"values": rinde, "mean": round(float(df["Rendimiento_Ton_Ha"].mean()), 2)},
    }
