"""
Esquemas Pydantic para Tratamiento y Prescripciones Médicas (Farmacología) — HU-016 y HU-017.
"""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator


TIPOS_TRATAMIENTO_VALIDOS = {
    "farmacologico",
    "quirurgico",
    "estilo_de_vida",
    "combinado",
    "otro",
    "farmacológico y estilo de vida"
}


class MedicacionIn(BaseModel):
    id: Optional[UUID] = None
    tratamiento_id: Optional[UUID] = None
    nombre_medicamento: str = Field(..., min_length=2, max_length=150, description="Nombre genérico o comercial del fármaco")
    dosis: str = Field(..., min_length=2, max_length=100, description="Posología prescrita (ej. 500 mg, 1 comprimido)")
    frecuencia: str = Field(..., min_length=2, max_length=100, description="Frecuencia de toma (ej. Cada 12 horas, Diaria con alimentos)")
    via_administracion: Optional[str] = "Oral"
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    activo: Optional[bool] = True
    indicaciones_especiales: Optional[str] = None

    @field_validator("nombre_medicamento")
    @classmethod
    def validar_nombre_medicamento(cls, v: str) -> str:
        v_clean = str(v).strip()
        if len(v_clean) < 2:
            raise ValueError("El nombre del medicamento debe tener al menos 2 caracteres.")
        if v_clean.isdigit():
            raise ValueError("El nombre del medicamento no puede ser puramente numérico.")
        return v_clean

    @field_validator("dosis")
    @classmethod
    def validar_dosis(cls, v: str) -> str:
        v_clean = str(v).strip()
        if len(v_clean) < 2:
            raise ValueError("La dosis debe contener al menos 2 caracteres.")
        return v_clean

    @field_validator("frecuencia")
    @classmethod
    def validar_frecuencia(cls, v: str) -> str:
        v_clean = str(v).strip()
        if len(v_clean) < 2:
            raise ValueError("La frecuencia debe contener al menos 2 caracteres.")
        return v_clean

    @model_validator(mode="after")
    def validar_coherencia_fechas(self):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValueError("La fecha de fin de la medicación debe ser estrictamente posterior a la fecha de inicio.")
        return self


class MedicacionOut(BaseModel):
    id: UUID
    tratamiento_id: UUID
    nombre_medicamento: str
    dosis: str
    frecuencia: str
    via_administracion: Optional[str] = "Oral"
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    activo: bool = True
    indicaciones_especiales: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlanTratamientoIn(BaseModel):
    paciente_id: UUID
    cita_id: Optional[UUID] = None
    tipo: Optional[str] = "farmacologico"
    descripcion: Optional[str] = None
    objetivo: Optional[str] = None
    duracion_semanas: Optional[int] = Field(24, ge=1, le=104, description="Duración estimada entre 1 y 104 semanas (máx 2 años)")
    observaciones: Optional[str] = None
    activo: Optional[bool] = True
    medicaciones: List[MedicacionIn] = Field(default_factory=list)

    @field_validator("tipo")
    @classmethod
    def validar_tipo_tratamiento(cls, v: Optional[str]) -> str:
        if not v:
            return "farmacologico"
        v_clean = str(v).strip().lower()
        if v_clean not in TIPOS_TRATAMIENTO_VALIDOS:
            raise ValueError(f"Tipo de tratamiento no válido. Debe ser uno de: {', '.join(sorted(TIPOS_TRATAMIENTO_VALIDOS))}")
        return v_clean

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = str(v).strip()
            if len(v_clean) > 0 and len(v_clean) < 3:
                raise ValueError("La descripción del tratamiento debe tener al menos 3 caracteres.")
            return v_clean
        return v

    @field_validator("objetivo")
    @classmethod
    def validar_objetivo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = str(v).strip()
            if len(v_clean) > 0 and len(v_clean) < 3:
                raise ValueError("El objetivo terapéutico debe tener al menos 3 caracteres.")
            return v_clean
        return v


class PlanTratamientoOut(BaseModel):
    id: Optional[UUID] = None
    paciente_id: UUID
    cita_id: Optional[UUID] = None
    tipo: Optional[str] = None
    descripcion: Optional[str] = None
    objetivo: Optional[str] = None
    duracion_semanas: Optional[int] = None
    observaciones: Optional[str] = None
    activo: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    medicaciones: List[MedicacionOut] = Field(default_factory=list)


class MedicacionRegistroRequest(BaseModel):
    tratamiento_id: UUID
    nombre_medicamento: str = Field(..., min_length=2, max_length=150)
    dosis: str = Field(..., min_length=2, max_length=100)
    frecuencia: str = Field(..., min_length=2, max_length=100)
    via_administracion: Optional[str] = "Oral"
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    activo: Optional[bool] = True
    indicaciones_especiales: Optional[str] = None

    @field_validator("nombre_medicamento")
    @classmethod
    def validar_nombre_medicamento(cls, v: str) -> str:
        v_clean = str(v).strip()
        if len(v_clean) < 2:
            raise ValueError("El nombre del medicamento debe tener al menos 2 caracteres.")
        if v_clean.isdigit():
            raise ValueError("El nombre del medicamento no puede ser puramente numérico.")
        return v_clean

    @model_validator(mode="after")
    def validar_coherencia_fechas(self):
        if self.fecha_inicio and self.fecha_fin:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValueError("La fecha de fin de la medicación debe ser estrictamente posterior a la fecha de inicio.")
        return self
