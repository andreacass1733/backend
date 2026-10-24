"""
Esquema Pydantic para Solicitud de Órdenes Médicas de Laboratorio y Ecografía.
Permite al médico prescribir estudios de sangre (hormonales y metabólicos)
y ecografía (transvaginal o pélvica/abdominal a base de agua según sexarca).
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class ExamenLaboratorioItem(BaseModel):
    codigo: str
    nombre: str
    categoria: str = "hormonal"  # 'hormonal', 'metabolico', 'diferencial', 'orina'
    seleccionado: bool = True


class OrdenMedicaCreate(BaseModel):
    paciente_id: str = Field(..., description="UUID de la paciente")
    consulta_id: Optional[str] = Field(None, description="UUID de la consulta asociada")
    medico_id: Optional[str] = Field(None, description="UUID del médico solicitante")
    
    # Estudio Ecográfico
    tipo_ecografia: str = Field("transvaginal", description="'transvaginal', 'pelvica_abdominal', 'doppler', 'ninguna'")
    indicacion_ecografia: Optional[str] = Field(None, description="Indicación técnica del estudio ecográfico")
    
    # Exámenes de Laboratorio
    examenes_laboratorio: List[Dict[str, Any]] = Field(default_factory=list, description="Lista de pruebas solicitadas")
    
    # Preparación e Indicaciones
    indicaciones_preanaliticas: Optional[str] = Field(None, description="Ayuno, días del ciclo, hidratación...")
    diagnostico_presuntivo: Optional[str] = Field(
        "Sospecha de Síndrome de Ovario Poliquístico (CIE-10: E28.2) — Protocolo Rotterdam",
        description="Diagnóstico orientativo"
    )
    prioridad: str = Field("normal", description="'normal', 'preferente', 'urgente'")
    observaciones: Optional[str] = None

    @field_validator("tipo_ecografia")
    @classmethod
    def validar_tipo_ecografia(cls, v: str) -> str:
        permitidos = ["transvaginal", "pelvica_abdominal", "doppler", "ninguna"]
        if v and v.lower() not in permitidos:
            raise ValueError(f"Tipo de ecografía inválido '{v}'. Permitidos: {', '.join(permitidos)}")
        return v.lower() if v else v

    @field_validator("prioridad")
    @classmethod
    def validar_prioridad(cls, v: str) -> str:
        permitidos = ["normal", "preferente", "urgente"]
        if v and v.lower() not in permitidos:
            raise ValueError(f"Prioridad inválida '{v}'. Permitidos: {', '.join(permitidos)}")
        return v.lower() if v else v

    @field_validator("indicacion_ecografia")
    @classmethod
    def validar_indicacion_ecografia(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "" and len(v.strip()) < 3:
            raise ValueError("La indicación ecográfica debe tener al menos 3 caracteres.")
        return v.strip() if v and v.strip() else None


class OrdenMedicaResponse(BaseModel):
    id: str
    paciente_id: str
    paciente_nombre: Optional[str] = None
    paciente_ci: Optional[str] = None
    consulta_id: Optional[str] = None
    medico_id: Optional[str] = None
    medico_nombre: Optional[str] = None
    medico_especialidad: Optional[str] = None
    medico_matricula: Optional[str] = None
    fecha_emision: str
    tipo_ecografia: str
    indicacion_ecografia: Optional[str] = None
    examenes_laboratorio: List[Dict[str, Any]] = []
    indicaciones_preanaliticas: Optional[str] = None
    diagnostico_presuntivo: Optional[str] = None
    estado: str = "vigente"
    prioridad: str = "normal"
    observaciones: Optional[str] = None
    created_at: Optional[str] = None


class OrdenMedicaListResponse(BaseModel):
    total: int
    ordenes: List[OrdenMedicaResponse]
