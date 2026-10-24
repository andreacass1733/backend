"""
Esquemas Pydantic para la Clasificación Fenotípica de Rotterdam y Validación Médica (HU-014, HU-015, HU-018).

Permite recibir la evaluación de los 3 criterios de Rotterdam:
  - Criterio 1: Disfunción ovulatoria (Oligo/Amenorrea)
  - Criterio 2: Hiperandrogenismo clínico y/o bioquímico
  - Criterio 3: Morfología ecográfica ovárica poliquística (PCOM)

Devuelve el fenotipo asignado (A, B, C, D o Sin SOP) con su desglose médico y permite
la confirmación o rectificación con justificación clínica firmada por el especialista.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator


FENOTIPOS_VALIDOS = {"Fenotipo A", "Fenotipo B", "Fenotipo C", "Fenotipo D", "Sin SOP"}


class ClasificacionRequest(BaseModel):
    paciente_id: Optional[str] = None
    cumple_criterio1: bool = Field(False, description="Disfunción ovulatoria (Oligomenorrea / Amenorrea)")
    cumple_criterio2: bool = Field(False, description="Hiperandrogenismo clínico o bioquímico")
    cumple_criterio3: bool = Field(False, description="Morfología ecográfica poliquística")
    probabilidad_criterio1: Optional[float] = Field(None, ge=0.0, le=1.0, description="Probabilidad de Criterio 1 [0.0 - 1.0]")
    probabilidad_criterio2: Optional[float] = Field(None, ge=0.0, le=1.0, description="Probabilidad de Criterio 2 [0.0 - 1.0]")
    probabilidad_criterio3: Optional[float] = Field(None, ge=0.0, le=1.0, description="Probabilidad de Criterio 3 [0.0 - 1.0]")
    observaciones: Optional[str] = None


class DetalleCriterioItem(BaseModel):
    cumple: bool
    nombre: str
    probabilidad: Optional[float] = None


class ClasificacionResponse(BaseModel):
    tiene_sop: bool
    fenotipo: str  # "Fenotipo A", "Fenotipo B", "Fenotipo C", "Fenotipo D", "Sin SOP"
    descripcion: str
    total_criterios_cumplidos: int
    desglose_criterios: Dict[str, Any]
    recomendacion_terapeutica: Optional[str] = None
    nivel_confianza: Optional[str] = "Alta"


class ConfirmarClasificacionRequest(BaseModel):
    paciente_id: str = Field(..., min_length=4, description="UUID o identificador de la paciente")
    consulta_id: Optional[str] = None
    fenotipo_sugerido: str = Field(..., description="Fenotipo propuesto inicialmente por el sistema")
    fenotipo_confirmado: str = Field(..., description="Fenotipo ratificado o rectificado por el médico")
    criterio1_cumple: bool = False
    criterio2_cumple: bool = False
    criterio3_cumple: bool = False
    es_modificado: bool = False
    justificacion_medica: Optional[str] = Field(None, description="Obligatoria si es_modificado es True")
    conducta_terapeutica: Optional[str] = None
    medico_nombre: Optional[str] = "Dr. Rodrigo Espinoza"

    @field_validator("fenotipo_confirmado")
    @classmethod
    def validar_fenotipo_confirmado(cls, v: str) -> str:
        v_clean = str(v).strip()
        if v_clean not in FENOTIPOS_VALIDOS:
            raise ValueError(f"Fenotipo '{v_clean}' no válido. Debe ser uno de: {', '.join(sorted(FENOTIPOS_VALIDOS))}")
        return v_clean

    @model_validator(mode="after")
    def validar_justificacion_modificacion(self):
        if self.es_modificado:
            just = str(self.justificacion_medica or "").strip()
            if len(just) < 5:
                raise ValueError("Debe ingresar una justificación médica explícita (mínimo 5 caracteres) cuando rectifica el fenotipo sugerido por el sistema.")
        return self


class ConfirmacionRotterdamResponse(BaseModel):
    exito: bool
    mensaje: str
    fecha: str
    paciente_id: str
    fenotipo_final: str
    es_modificado: bool
    auditoria_registrada: bool
