"""
Router del Criterio 1 - Disfunción Ovulatoria (Oligo/Anovulación).

Rutas:
  - POST /criterio1/evaluar: Evalúa si la paciente cumple el primer criterio de Rotterdam.
"""

from fastapi import APIRouter
from typing import Dict, Any
from services.rotterdam_ia.criterio1_service import run_prediction

router = APIRouter(prefix="/criterio1", tags=["Criterio 1 - Disfunción Ovulatoria"])


@router.post("/evaluar")
def evaluar_criterio1(datos: Dict[str, Any]):
    """Evalúa el Criterio 1 a partir de variables clínicas del ciclo menstrual y progesterona."""
    return run_prediction(datos)


@router.get("/")
def info():
    return {
        "criterio": "Criterio 1 — Disfunción Ovulatoria (Oligo/Anovulación)",
        "estado": "Operativo",
        "descripcion": "Evaluación de regularidad del ciclo, duración >35 días, amenorrea y progesterona lútea."
    }
