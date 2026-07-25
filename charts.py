"""
Gráficas analíticas con Matplotlib y Seaborn.

Cada función recibe un DataFrame ya filtrado y devuelve un PNG codificado en
base64 (data URI) listo para incrustar en el HTML. Se usa el backend 'Agg'
(sin ventana) porque corren dentro del servidor Flask.

El estilo replica el sistema visual del dashboard (tema agro): superficie clara,
tinta verde plantación y una rampa secuencial verde de marca.
"""
from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

from data_utils import NIVEL_ORDEN

# --- Sistema de color de las gráficas (coherente con la página) ------------- #
SURFACE = "#fbfcf8"
INK = "#17251a"
MUTED = "#6b7a63"
GRID = "#e4e8dc"
GREEN = "#2e6b3e"

# Rampa secuencial verde de marca (claro -> plantación -> oscuro).
GREEN_SEQ = LinearSegmentedColormap.from_list(
    "agro_green", ["#dcebd8", "#7db487", "#3f7f4d", "#2e6b3e", "#16351f"]
)
# Divergente para la matriz de correlación (azul <-> gris <-> rojo).
DIVERGING = LinearSegmentedColormap.from_list(
    "agro_div", ["#2a78d6", "#eef1ea", "#e34948"]
)
# Cuatro verdes discretos para el eje ordinal de tecnificación.
NIVEL_COLORS = ["#cfe3d0", "#7db487", "#3f7f4d", "#16351f"]


def _rc():
    """Aplica el estilo base de Matplotlib para todas las gráficas."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 11,
        "font.family": "DejaVu Sans",
    })


def _fig_to_uri(fig) -> str:
    """Serializa la figura a un data URI PNG y libera memoria."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _empty(msg: str = "Sin datos para los filtros") -> str:
    _rc()
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.text(0.5, 0.5, msg, ha="center", va="center", color=MUTED, fontsize=13)
    ax.axis("off")
    return _fig_to_uri(fig)


def correlation_heatmap(df) -> str:
    """Matriz de correlación de las variables numéricas (Seaborn)."""
    cols = ["Area_Hectareas", "Produccion_Anual_Ton",
            "Precio_Venta_Por_Ton_COP", "Rendimiento_Ton_Ha",
            "Ingreso_Estimado_COP"]
    if df.shape[0] < 3:
        return _empty()
    _rc()
    labels = ["Área", "Producción", "Precio", "Rendimiento", "Ingreso"]
    corr = df[cols].corr()
    fig, ax = plt.subplots(figsize=(6.2, 5))
    sns.heatmap(
        corr, annot=True, fmt=".2f", cmap=DIVERGING, vmin=-1, vmax=1,
        center=0, square=True, linewidths=2, linecolor=SURFACE,
        cbar_kws={"shrink": 0.8, "label": "Correlación (r)"},
        xticklabels=labels, yticklabels=labels, ax=ax,
        annot_kws={"fontsize": 10, "color": INK},
    )
    ax.set_title("Correlación entre variables numéricas", pad=14,
                 fontsize=13, fontweight="bold", loc="left")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    plt.setp(ax.get_yticklabels(), rotation=0)
    return _fig_to_uri(fig)


def production_by_tech_box(df) -> str:
    """Distribución de la producción según el nivel de tecnificación (boxplot)."""
    if df.shape[0] < 3:
        return _empty()
    _rc()
    niveles = [n for n in NIVEL_ORDEN if (df["Nivel_Tecnificacion"] == n).any()]
    # Paleta como diccionario por nivel: robusta aunque el filtro deje <4 niveles
    # (el dtype categórico siempre reporta las 4 categorías).
    palette = {n: NIVEL_COLORS[NIVEL_ORDEN.index(n)] for n in NIVEL_ORDEN}
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    sns.boxplot(
        data=df, x="Nivel_Tecnificacion", y="Produccion_Anual_Ton",
        order=niveles, hue="Nivel_Tecnificacion", legend=False,
        palette=palette, width=0.6, linewidth=1.3,
        fliersize=3, ax=ax,
    )
    sns.stripplot(
        data=df, x="Nivel_Tecnificacion", y="Produccion_Anual_Ton",
        order=niveles, color=INK, alpha=0.25, size=3, jitter=0.2, ax=ax,
    )
    ax.set_title("Producción anual por nivel de tecnificación", pad=12,
                 fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel("")
    ax.set_ylabel("Producción anual (Ton)")
    return _fig_to_uri(fig)


def yield_distribution(df) -> str:
    """Distribución del rendimiento (Ton/ha) con histograma + KDE (Matplotlib)."""
    if df.shape[0] < 3:
        return _empty()
    _rc()
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    sns.histplot(
        df["Rendimiento_Ton_Ha"], bins=24, kde=True, color=GREEN,
        edgecolor=SURFACE, linewidth=1.2, alpha=0.85,
        line_kws={"linewidth": 2.2}, ax=ax,
    )
    if ax.lines:
        ax.lines[-1].set_color("#16351f")
    media = df["Rendimiento_Ton_Ha"].mean()
    ax.axvline(media, color="#a5352a", linestyle="--", linewidth=1.8)
    ax.text(media, ax.get_ylim()[1] * 0.92, f"  media {media:.1f}",
            color="#a5352a", fontsize=10, fontweight="bold")
    ax.set_title("Distribución del rendimiento (Ton/ha)", pad=12,
                 fontsize=13, fontweight="bold", loc="left")
    ax.set_xlabel("Rendimiento (Ton/ha)")
    ax.set_ylabel("Nº de fincas")
    return _fig_to_uri(fig)


def build_all(df) -> dict:
    """Genera las tres gráficas estáticas de una pasada."""
    return {
        "heatmap": correlation_heatmap(df),
        "boxplot": production_by_tech_box(df),
        "hist": yield_distribution(df),
    }
