from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date

ESTADOS_VALIDOS = {"programada", "atendida", "cancelada", "no asistió", "no_asistio"}

class CitaBase(BaseModel):
    paciente_id: Optional[str] = None
    medico_id: Optional[str] = None
    fecha_atencion: Optional[datetime] = None
    fecha_proxima_cita: Optional[str] = None
    motivo: Optional[str] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = "programada"

    @field_validator("motivo")
    @classmethod
    def validar_motivo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 3:
                raise ValueError("El motivo de la cita debe tener al menos 3 caracteres.")
            if len(clean) > 500:
                raise ValueError("El motivo de la cita excede la longitud máxima permitida (500 caracteres).")
            return clean
        return v

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if clean not in ESTADOS_VALIDOS:
                raise ValueError(
                    f"Estado de cita '{v}' inválido. Debe ser: programada, atendida, cancelada o no asistió."
                )
            return clean
        return v


class CitaCreate(CitaBase):
    pass


class CitaUpdate(BaseModel):
    paciente_id: Optional[str] = None
    medico_id: Optional[str] = None
    fecha_atencion: Optional[datetime] = None
    fecha_proxima_cita: Optional[str] = None
    motivo: Optional[str] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = None

    @field_validator("motivo")
    @classmethod
    def validar_motivo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean) < 3:
                raise ValueError("El motivo de la cita debe tener al menos 3 caracteres.")
            if len(clean) > 500:
                raise ValueError("El motivo de la cita excede la longitud máxima permitida (500 caracteres).")
            return clean
        return v

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if clean not in ESTADOS_VALIDOS:
                raise ValueError(
                    f"Estado de cita '{v}' inválido. Debe ser: programada, atendida, cancelada o no asistió."
                )
            return clean
        return v


class CitaResponse(CitaBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
