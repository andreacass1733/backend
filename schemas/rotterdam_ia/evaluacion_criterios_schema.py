"""
Esquemas Pydantic para la Evaluación mediante XGBoost (HU-013).

Evalúa el Criterio 1 (Disfunción ovulatoria) y Criterio 2 (Hiperandrogenismo)
de forma independiente a partir de las variables clínicas y hormonales.
Devuelve resultado, probabilidad y factores determinantes sin clasificar fenotipo.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from schemas.rotterdam_ia.datos_hormonales_schema import DatosHormonalesIn
from schemas.rotterdam_ia.datos_clinicos_schema import DatosClinicosIn


class EvaluacionXGBoostRequest(BaseModel):
    consulta_id: Optional[str] = None
    paciente_id: Optional[str] = None
    datos_hormonales: Optional[DatosHormonalesIn] = None
    datos_clinicos: Optional[DatosClinicosIn] = None


class DetalleCriterio(BaseModel):
    nombre: str
    cumple: bool
    resultado: str  # "Cumple criterio" | "No cumple criterio"
    probabilidad: float  # 0.0 a 100.0%
    indicador_color: str  # "rojo" (cumple patológico) | "verde" (normal)
    factores_determinantes: List[str]
    interpretacion_medica: str


class EvaluacionXGBoostResponse(BaseModel):
    consulta_id: Optional[str] = None
    paciente_id: Optional[str] = None
    fecha_evaluacion: str

    criterio_1: DetalleCriterio  # Disfunción ovulatoria (Oligo/Anovulación)
    criterio_2: DetalleCriterio  # Hiperandrogenismo clínico y/o bioquímico

    datos_ingresados: Dict[str, Any]  # Resumen de lo ingresado por el médico para verificación
    modelo_info: Dict[str, Any]  # Versión, algoritmo, status de imputación
    error: bool = False
    mensaje: Optional[str] = None
