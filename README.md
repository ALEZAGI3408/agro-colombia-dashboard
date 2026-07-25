# Dashboard AgroColombia

Panel interactivo local (Flask) para el análisis exploratorio del dataset
`agro_colombia.csv` (500 fincas agrícolas colombianas). Cubre: carga y limpieza
de datos, EDA, storytelling por variable, gráficas con **Seaborn, Matplotlib y
Plotly**, y generación de un **reporte HTML descargable**.

## Requisitos

- Python 3.10+
- Conexión a internet la primera vez (fuentes de Google + librería Plotly por CDN)

## Instalación y ejecución

```bash
pip install -r requirements.txt
python app.py
```

Luego abre **http://127.0.0.1:5000** en el navegador.

## Qué hace

- **Filtros dinámicos** por departamento, cultivo, nivel de tecnificación y riego;
  todo el panel (KPIs, gráficas, insights, tabla) se recalcula en vivo.
- **Sección interactiva (Plotly):** producción por departamento, precio por
  cultivo, dispersión área–producción y dona de tecnificación.
- **Sección analítica (Seaborn/Matplotlib):** matriz de correlación, boxplot de
  producción por tecnificación e histograma+KDE del rendimiento.
- **Síntesis:** hallazgos narrativos generados desde los datos + `describe()` +
  botón para descargar el reporte HTML.

## Estructura

| Archivo | Rol |
|---|---|
| `app.py` | Servidor Flask y rutas API |
| `data_utils.py` | Carga, limpieza, imputación, agregaciones e insights |
| `charts.py` | Gráficas Seaborn/Matplotlib (PNG base64) |
| `report.py` | Reporte HTML descargable |
| `templates/index.html` | Estructura del dashboard |
| `static/css/style.css` | Sistema visual (tema agro andino) |
| `static/js/dashboard.js` | Filtros, Plotly y llamadas a la API |

## Limpieza aplicada

Fecha de auditoría a `datetime`, nivel de tecnificación como categórica ordenada
(`Bajo < Medio < Alto < Muy Alto`), imputación por mediana de cultivo como red de
seguridad, deduplicación por `ID_Finca`, y dos columnas derivadas:
`Rendimiento_Ton_Ha` e `Ingreso_Estimado_COP`.
