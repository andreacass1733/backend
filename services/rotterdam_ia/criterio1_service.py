"""
Servicio del Criterio 1 de Rotterdam: Disfunción Ovulatoria (Oligo/Anovulación).

Evalúa si la paciente cumple el primer criterio de Rotterdam a partir
de signos clínicos del ciclo menstrual (amenorrea, oligomenorrea, ciclos irregulares)
y biomarcadores hormonales (progesterona lútea, relación LH/FSH).
"""

from typing import Dict, Any, Optional
from services.rotterdam_ia.evaluacion_service import _evaluar_criterio_1_disfuncion_ovulatoria


def run_prediction(datos: dict) -> Dict[str, Any]:
    """
    Ejecuta la evaluación del Criterio 1 a partir de las variables clínicas y hormonales.

    Args:
        datos (dict): Contiene variables clínicas ('clinicos') y/o hormonales ('hormonales')
                      o un diccionario plano con los atributos del paciente.

    Returns:
        dict: Resultado con probabilidad, veredicto (Cumple/No cumple) y factores determinantes.
    """
    clinicos = datos.get("clinicos", datos)
    hormonales = datos.get("hormonales", datos)

    resultado = _evaluar_criterio_1_disfuncion_ovulatoria(clinicos, hormonales)
    return resultado.model_dump()
