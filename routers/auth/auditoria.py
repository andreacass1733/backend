"""
Router para Registro de Auditoría Médica, Seguridad y Trazabilidad de IA (Audit Logs).
Cumplimiento estricto HIPAA Security Rule y NOM-024-SSA3.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from schemas.auth.auditoria_schema import (
    AuditoriaListResponse,
    AuditoriaMetricas,
    AuditLogItem
)
from services.auth.auditoria_service import (
    listar_eventos_auditoria,
    obtener_metricas_auditoria,
    registrar_evento_auditoria
)

router = APIRouter(prefix="/auditoria", tags=["Auditoría y Trazabilidad (Audit Logs)"])


@router.get("/logs", response_model=AuditoriaListResponse)
def consultar_logs(
    q: Optional[str] = Query(None, description="Búsqueda por paciente, IP, usuario o hash"),
    modulo: Optional[str] = Query(None, description="Filtro por módulo clínico"),
    nivel: Optional[str] = Query(None, description="Filtro por nivel o estado del log"),
    fecha: Optional[str] = Query(None, description="Filtro por fecha YYYY-MM-DD o DD/MM/YYYY"),
    limite: int = Query(100, ge=1, le=500, description="Límite de registros a retornar")
):
    try:
        return listar_eventos_auditoria(
            busqueda=q,
            modulo=modulo,
            nivel=nivel,
            fecha=fecha,
            limite=limite
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando logs de auditoría: {str(e)}")


@router.get("/metricas", response_model=AuditoriaMetricas)
def consultar_metricas():
    try:
        return obtener_metricas_auditoria()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas de auditoría: {str(e)}")
