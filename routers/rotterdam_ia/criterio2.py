"""
Router del Criterio 2 - Hiperandrogenismo Clínico y/o Bioquímico.

Rutas:
  - POST /criterio2/evaluar: Evalúa si la paciente cumple el segundo criterio de Rotterdam con XGBoost.
"""

from fastapi import APIRouter
from typing import Dict, Any
from services.rotterdam_ia.criterio2_service import run_prediction

router = APIRouter(prefix="/criterio2", tags=["Criterio 2 - Hiperandrogenismo"])


@router.post("/evaluar")
def evaluar_criterio2(datos: Dict[str, Any]):
    """Evalúa el Criterio 2 mediante el modelo XGBoost y reglas clínicas de hiperandrogenismo."""
    return run_prediction(datos)


@router.get("/")
def info():
    return {
        "criterio": "Criterio 2 — Hiperandrogenismo Clínico / Bioquímico (XGBoost)",
        "estado": "Operativo",
        "descripcion": "Evaluación de andrógenos séricos, hirsutismo (Ferriman-Gallwey), acné y alopecia con IA."
    }


@router.get("/metricas-clinicas")
def obtener_metricas_criterio2():
    """Retorna las métricas de validación del XGBoost clínico (Rotterdam)."""
    import os
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    posibles_rutas = [
        os.path.join(base_dir, 'models_ia', 'xgboost', 'metricas_clinicas.json'),
        os.path.join(base_dir, "outputs", "evaluacion_clinica", "metricas_clinicas.json"),
        os.path.join(base_dir, "pipelines", "xgboost", "evaluacion_clinica", "metricas_clinicas.json")
    ]
    for r in posibles_rutas:
        if os.path.exists(r):
            with open(r, "r", encoding="utf-8") as f:
                return json.load(f)
    return {"status": "Métricas no generadas aún"}
