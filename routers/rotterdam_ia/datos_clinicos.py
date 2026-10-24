"""
Router de la API para Datos Clínicos y Antropométricos (HU-010).

Rutas:
  - POST /clinicos: Guarda o actualiza signos de hiperandrogenismo, antropometría y presión arterial.
  - GET  /clinicos/{consulta_id}: Consulta los datos clínicos guardados para una consulta.
  - POST /clinicos/metricas-preview: Calcula IMC y relación cintura/cadera en tiempo real para el frontend.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from schemas.rotterdam_ia.datos_clinicos_schema import (
    DatosClinicosIn,
    DatosClinicosOut
)
from services.rotterdam_ia.datos_clinicos_service import (
    guardar_datos_clinicos,
    obtener_datos_clinicos,
    obtener_ultimos_datos_clinicos_paciente,
    calcular_metricas_antropometricas
)

router = APIRouter(prefix="/clinicos", tags=["Datos Clínicos (HU-010)"])


@router.post("/", response_model=DatosClinicosOut)
def registrar_o_actualizar_datos_clinicos(payload: DatosClinicosIn):
    """
    Registra o actualiza los datos clínicos y signos de hiperandrogenismo.
    Valida estrictamente que el score Ferriman-Gallwey esté entre 0 y 36.
    Calcula automáticamente el IMC y devuelve mensaje de confirmación.
    """
    try:
        resultado = guardar_datos_clinicos(payload)
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar datos clínicos: {str(e)}"
        )


@router.get("/paciente/{paciente_id}", response_model=Optional[DatosClinicosOut])
def consultar_datos_clinicos_paciente(paciente_id: str):
    """Obtiene los últimos datos clínicos y signos vitales registrados para una paciente."""
    datos = obtener_ultimos_datos_clinicos_paciente(paciente_id)
    return datos


@router.get("/{consulta_id}", response_model=DatosClinicosOut)
def consultar_datos_clinicos(consulta_id: str):
    """Obtiene los datos clínicos registrados para una consulta médica."""
    datos = obtener_datos_clinicos(consulta_id)
    if not datos:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron datos clínicos para la consulta {consulta_id}."
        )
    return datos


@router.post("/metricas-preview")
def preview_metricas(payload: DatosClinicosIn):
    """
    Calcula el IMC y la relación cintura/cadera en tiempo real
    sin persistir en la base de datos.
    """
    try:
        raw = payload.model_dump(exclude_unset=True)
        fg = raw.get("score_ferriman_gallwey")
        if fg is not None and (int(fg) < 0 or int(fg) > 36):
            raise HTTPException(
                status_code=400,
                detail="El score Ferriman-Gallwey debe aceptar únicamente valores entre 0 y 36."
            )
        procesado = calcular_metricas_antropometricas(raw)
        return procesado
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
