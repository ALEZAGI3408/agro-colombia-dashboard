"""
Punto de entrada para Vercel (función serverless de Python).

Vercel detecta los archivos dentro de /api como funciones. Añadimos la raíz
del proyecto al path e importamos la app Flask, que expone el objeto WSGI `app`.
En este entorno Matplotlib/Seaborn no están instaladas, así que app.py corre en
modo ligero (gráficas analíticas con Plotly.js).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (WSGI callable que Vercel ejecuta)
