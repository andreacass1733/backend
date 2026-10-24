"""
Router de la API para Datos Hormonales (HU-009).

Rutas:
  - POST /hormonales: Guarda o actualiza datos hormonales por consulta.
  - GET  /hormonales/{consulta_id}: Consulta datos hormonales existentes con su semáforo.
  - POST /hormonales/semaforo-preview: Calcula semáforos y métricas en tiempo real para el frontend.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from schemas.rotterdam_ia.datos_hormonales_schema import (
    DatosHormonalesIn,
    DatosHormonalesOut
)
from services.rotterdam_ia.datos_hormonales_service import (
    guardar_datos_hormonales,
    obtener_datos_hormonales,
    obtener_ultimos_datos_hormonales_paciente,
    generar_semaforo_completo,
    calcular_calculos_automaticos
)

router = APIRouter(prefix="/hormonales", tags=["Datos Hormonales (HU-009)"])


@router.post("/", response_model=DatosHormonalesOut)
def registrar_o_actualizar_datos_hormonales(payload: DatosHormonalesIn):
    """
    Registra o actualiza los datos hormonales de la paciente en una consulta.
    Calcula automáticamente HOMA-IR y la relación LH/FSH.
    Genera el semáforo de referencia clínico.
    """
    try:
        resultado = guardar_datos_hormonales(payload)
        return resultado
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar datos hormonales: {str(e)}"
        )


@router.get("/paciente/{paciente_id}", response_model=Optional[DatosHormonalesOut])
def consultar_datos_hormonales_paciente(paciente_id: str):
    """Obtiene el último perfil hormonal registrado para la paciente indicada."""
    datos = obtener_ultimos_datos_hormonales_paciente(paciente_id)
    return datos


@router.get("/{consulta_id}", response_model=DatosHormonalesOut)
def consultar_datos_hormonales(consulta_id: str):
    """Obtiene los datos hormonales registrados para la consulta indicada."""
    datos = obtener_datos_hormonales(consulta_id)
    if not datos:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron datos hormonales para la consulta {consulta_id}."
        )
    return datos


@router.post("/semaforo-preview")
def preview_semaforo(payload: DatosHormonalesIn):
    """
    Calcula los semáforos clínicos y valores automáticos (HOMA-IR, LH/FSH)
    en memoria sin necesidad de persistir en base de datos.
    """
    raw = payload.model_dump(exclude_unset=True)
    procesado = calcular_calculos_automaticos(raw)
    semaforo = generar_semaforo_completo(procesado)
    return {
        "datos": procesado,
        "semaforo": semaforo
    }
