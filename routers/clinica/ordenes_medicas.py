"""
Router para Emisión y Gestión de Órdenes Médicas de Laboratorio y Ecografía (HU-021).
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from schemas.clinica.orden_medica_schema import OrdenMedicaCreate, OrdenMedicaResponse, OrdenMedicaListResponse
from services.clinica.orden_medica_service import (
    crear_orden_medica,
    obtener_ordenes_por_paciente,
    obtener_orden_por_id,
    cancelar_orden_medica
)

router = APIRouter(prefix="/ordenes-medicas", tags=["Órdenes Médicas (Laboratorio y Ecografía)"])


@router.post("/", response_model=OrdenMedicaResponse)
@router.post("", response_model=OrdenMedicaResponse)
def emitir_orden(datos: OrdenMedicaCreate):
    """
    Emite una nueva orden médica con exámenes hormonales, metabólicos y estudio ecográfico.
    """
    try:
        return crear_orden_medica(datos)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al emitir orden médica: {str(e)}")


@router.get("/paciente/{paciente_id}", response_model=List[OrdenMedicaResponse])
def listar_por_paciente(paciente_id: str):
    """
    Lista el historial de órdenes médicas emitidas para una paciente.
    """
    try:
        return obtener_ordenes_por_paciente(paciente_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando órdenes médicas: {str(e)}")


@router.get("/{orden_id}", response_model=OrdenMedicaResponse)
def consultar_por_id(orden_id: str):
    """
    Obtiene los datos completos de una orden médica específica.
    """
    try:
        orden = obtener_orden_por_id(orden_id)
        if not orden:
            raise HTTPException(status_code=404, detail="Orden médica no encontrada")
        return orden
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando orden médica: {str(e)}")


@router.delete("/{orden_id}")
def cancelar_orden(orden_id: str):
    """
    Cancela una orden médica vigente.
    """
    try:
        exito = cancelar_orden_medica(orden_id)
        if not exito:
            raise HTTPException(status_code=404, detail="Orden médica no encontrada para cancelar")
        return {"status": "ok", "message": "Orden médica cancelada con éxito"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al cancelar orden médica: {str(e)}")
