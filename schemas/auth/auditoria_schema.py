"""
Esquemas Pydantic para el Registro de Auditoría Médica, Seguridad y Trazabilidad de IA (Audit Logs).
Cumplimiento de HIPAA Security Rule (45 CFR § 164.312(b)) y NOM-024-SSA3.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class AuditLogItem(BaseModel):
    id: str = Field(..., description="Identificador único del evento o folio forense")
    timestamp: str = Field(..., description="Marca de tiempo en formato ISO 8601")
    usuario: str = Field(..., description="Nombre del profesional o daemon que ejecutó la acción")
    rol: str = Field(..., description="Rol clínico o de sistema (ej. Gineco-Obstetra, Motor de IA)")
    ip: str = Field(..., description="Dirección IP de origen")
    estacion: str = Field(..., description="Dispositivo, consultorio o servicio de origen")
    modulo: str = Field(..., description="Módulo afectado (ej. ECOGRAFIA_CRIT3, EVALUACION_IA, AUTH_SERVICE)")
    evento: str = Field(..., description="Identificador del evento (ej. VALIDATE_STUDY, RUN_PREDICTION)")
    paciente_id: Optional[str] = Field(None, description="Expediente o ID de la paciente afectada")
    paciente_nombre: Optional[str] = Field(None, description="Nombre de la paciente o '— (Sesión de Sistema)'")
    detalle: str = Field(..., description="Descripción forense del evento registrado")
    hash_sha256: str = Field(..., description="Firma criptográfica SHA-256 inmutable de integridad")
    estado: str = Field(..., description="Estado del log: AUDIT_OK, AI_EXEC, LOCKED, AUTH_OK, ALERT_WARN")
    payload_json: Dict[str, Any] = Field(default_factory=dict, description="Payload completo JSON del evento")


class AuditoriaMetricas(BaseModel):
    eventos_totales_hoy: int = Field(..., description="Total de eventos auditados durante la jornada")
    trazabilidad_activa_pct: float = Field(100.0, description="Porcentaje de trazabilidad activa garantizada")
    inferencias_ia_registradas: int = Field(..., description="Total de ejecuciones de modelos IA")
    inferencias_subtitulo: str = Field("Criterios 1-2 + Red Neuronal", description="Detalle de modelos IA")
    validaciones_medicas: int = Field(..., description="Total de validaciones firmadas por médicos")
    validaciones_subtitulo: str = Field("Firma Humana Verificada", description="Detalle de verificación humana")
    alertas_seguridad: int = Field(..., description="Incidentes o intentos bloqueados de seguridad")
    alertas_subtitulo: str = Field("Intentos 2FA o accesos prevenidos", description="Detalle de incidentes")


class AuditoriaListResponse(BaseModel):
    total: int
    metricas: AuditoriaMetricas
    logs: List[AuditLogItem]
