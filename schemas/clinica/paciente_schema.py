"""
Esquemas Pydantic — Módulo de Pacientes y Antecedentes Médicos.

Define la validación de entrada y salida con restricciones clínicas avanzadas para:
  - Crear/editar pacientes (validación de nombres, CI único, rango de edad fisiológico, teléfono, email)
  - Listar pacientes con paginación y búsqueda
  - Crear/editar antecedentes médicos (coherencia obstétrica, menarquia, tipo de ciclo, historial versionado)
"""

from datetime import date, datetime, timedelta
import re
from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# Expresiones regulares para validación de formato
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
CI_REGEX = re.compile(r"^[a-zA-Z0-9\.\-\s]{4,20}$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-]{7,20}$")
NAME_REGEX = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\']{2,100}$")


# ══════════════════════════════════════════════════════════════════════════════
# PACIENTE
# ══════════════════════════════════════════════════════════════════════════════

class PacienteCreate(BaseModel):
    """Datos para registrar un nuevo paciente con validaciones estrictas."""
    nombre: str = Field(..., min_length=2, max_length=100)
    primer_apellido: str = Field(..., min_length=2, max_length=100)
    segundo_apellido: Optional[str] = Field(None, max_length=100)
    fecha_nacimiento: Optional[date] = None
    ci: Optional[str] = Field(None, max_length=20, description="Cédula de identidad única")
    telefono: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=150)
    medico_id: Optional[UUID] = Field(None, description="ID del médico tratante")

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres.")
        if clean.isdigit():
            raise ValueError("El nombre no puede ser puramente numérico.")
        if not NAME_REGEX.match(clean):
            raise ValueError("El nombre contiene caracteres especiales o símbolos no permitidos.")
        return clean

    @field_validator("primer_apellido")
    @classmethod
    def validar_primer_apellido(cls, v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 2:
            raise ValueError("El primer apellido debe tener al menos 2 caracteres.")
        if clean.isdigit():
            raise ValueError("El primer apellido no puede ser puramente numérico.")
        if not NAME_REGEX.match(clean):
            raise ValueError("El primer apellido contiene caracteres especiales o símbolos no permitidos.")
        return clean

    @field_validator("segundo_apellido")
    @classmethod
    def validar_segundo_apellido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if clean.isdigit():
            raise ValueError("El segundo apellido no puede ser puramente numérico.")
        if not NAME_REGEX.match(clean):
            raise ValueError("El segundo apellido contiene caracteres especiales no permitidos.")
        return clean

    @field_validator("ci")
    @classmethod
    def validar_ci(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if len(clean) < 4:
            raise ValueError("El CI debe tener al menos 4 caracteres.")
        if len(clean) > 20:
            raise ValueError("El CI no puede exceder los 20 caracteres.")
        if not CI_REGEX.match(clean):
            raise ValueError("Formato de CI inválido. Solo se permiten números, letras, puntos y guiones.")
        return clean

    @field_validator("fecha_nacimiento")
    @classmethod
    def validar_fecha_nacimiento(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            hoy = date.today()
            if v > hoy:
                raise ValueError("La fecha de nacimiento no puede ser una fecha futura.")
            # Restricción biológica: máximo 120 años de edad
            if v < hoy - timedelta(days=365 * 120):
                raise ValueError("La fecha de nacimiento no es válida (edad superior a 120 años).")
        return v

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if not PHONE_REGEX.match(clean):
            raise ValueError("Formato de teléfono inválido. Debe contener entre 7 y 20 dígitos numéricos.")
        return clean

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if not clean:
            return None
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Formato de correo electrónico inválido.")
        return clean


class PacienteUpdate(BaseModel):
    """Datos editables de un paciente con las mismas validaciones rigurosas."""
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    primer_apellido: Optional[str] = Field(None, min_length=2, max_length=100)
    segundo_apellido: Optional[str] = Field(None, max_length=100)
    fecha_nacimiento: Optional[date] = None
    ci: Optional[str] = Field(None, max_length=20)
    telefono: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=150)
    medico_id: Optional[UUID] = None
    activo: Optional[bool] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres.")
        if clean.isdigit():
            raise ValueError("El nombre no puede ser puramente numérico.")
        if not NAME_REGEX.match(clean):
            raise ValueError("El nombre contiene caracteres especiales o símbolos no permitidos.")
        return clean

    @field_validator("primer_apellido")
    @classmethod
    def validar_primer_apellido(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("El primer apellido debe tener al menos 2 caracteres.")
        if clean.isdigit():
            raise ValueError("El primer apellido no puede ser puramente numérico.")
        if not NAME_REGEX.match(clean):
            raise ValueError("El primer apellido contiene caracteres especiales no permitidos.")
        return clean

    @field_validator("ci")
    @classmethod
    def validar_ci(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if len(clean) < 4:
            raise ValueError("El CI debe tener al menos 4 caracteres.")
        if not CI_REGEX.match(clean):
            raise ValueError("Formato de CI inválido.")
        return clean

    @field_validator("fecha_nacimiento")
    @classmethod
    def validar_fecha_nacimiento(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            hoy = date.today()
            if v > hoy:
                raise ValueError("La fecha de nacimiento no puede ser una fecha futura.")
            if v < hoy - timedelta(days=365 * 120):
                raise ValueError("La fecha de nacimiento no es válida (edad superior a 120 años).")
        return v

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if not clean:
            return None
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Formato de correo electrónico inválido.")
        return clean


class PacienteOut(BaseModel):
    """Respuesta completa de un paciente."""
    id: UUID
    nombre: str
    primer_apellido: str
    segundo_apellido: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    ci: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    medico_id: Optional[UUID] = None
    activo: bool
    historial: Optional[Union[dict, list]] = None
    created_at: datetime
    updated_at: datetime

    @property
    def nombre_completo(self) -> str:
        partes = [self.nombre, self.primer_apellido]
        if self.segundo_apellido:
            partes.append(self.segundo_apellido)
        return " ".join(partes)


class PacienteListItem(BaseModel):
    """Versión reducida para listados con email y médico asociado."""
    id: UUID
    nombre: str
    primer_apellido: str
    segundo_apellido: Optional[str] = None
    ci: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    activo: bool
    medico_id: Optional[UUID] = None
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════════
# ANTECEDENTES MÉDICOS CON COHERENCIA GINECO-OBSTÉTRICA ESTRICTA
# ══════════════════════════════════════════════════════════════════════════════

class AntecedentesCreate(BaseModel):
    """Datos para crear los antecedentes médicos de un paciente con reglas de negocio clínicas."""
    paciente_id: UUID

    # Sexarca (Inicio de vida sexual)
    iniciada_vida_sexual: bool = Field(False, description="Indica si la paciente ha iniciado vida sexual")

    # Historial gineco-obstétrico
    edad_menarquia: Optional[int] = Field(None, ge=8, le=20, description="Edad de primera menstruación (8 a 20 años)")
    tipo_ciclo: Optional[str] = Field(None, description="regular / irregular / amenorrea / oligomenorrea")
    duracion_ciclo_habitual: Optional[int] = Field(None, ge=1, le=90, description="Días del ciclo habitual (1 a 90 días)")

    # Obstétrico
    gestas: int = Field(0, ge=0, description="Número de embarazos totales")
    partos: int = Field(0, ge=0, description="Partos vaginales")
    cesareas: int = Field(0, ge=0, description="Partos por cesárea")
    abortos: int = Field(0, ge=0, description="Pérdidas gestacionales")
    hijos_vivos: int = Field(0, ge=0, description="Hijos nacidos vivos sobrevivientes")

    # Anticonceptivos
    usa_anticonceptivos: bool = False
    tipo_anticonceptivo: Optional[str] = Field(None, max_length=100)

    # Antecedentes familiares
    familiar_con_sop: bool = False
    familiar_con_diabetes: bool = False

    # Antecedentes personales
    diabetes: bool = False
    hipotiroidismo: bool = False
    hiperprolactinemia: bool = False
    resistencia_insulina: bool = False

    # Alergias farmacológicas / generales
    alergias: Optional[str] = Field("Ninguna conocida", description="Alergias o intolerancias medicamentosas")

    # Notas y campo historial jsonb
    observaciones: Optional[str] = Field(None, max_length=1000)
    historial: Optional[Union[dict, list]] = None

    @field_validator("tipo_ciclo")
    @classmethod
    def validar_tipo_ciclo(cls, v):
        if v is not None and v not in {"regular", "irregular", "amenorrea", "oligomenorrea"}:
            raise ValueError("tipo_ciclo debe ser: regular, irregular, amenorrea u oligomenorrea")
        return v

    @model_validator(mode="after")
    def validar_coherencia_obstetrica(self):
        """Regla clínica: Total gestas >= partos + cesáreas + abortos."""
        partos = self.partos or 0
        cesareas = self.cesareas or 0
        abortos = self.abortos or 0
        gestas = self.gestas or 0
        hijos_vivos = self.hijos_vivos or 0

        total_desenlaces = partos + cesareas + abortos
        if total_desenlaces > gestas:
            raise ValueError(
                f"Incoherencia obstétrica: La suma de partos ({partos}), cesáreas ({cesareas}) y abortos ({abortos}) "
                f"[{total_desenlaces}] no puede ser mayor al número total de gestas ({gestas})."
            )

        if not self.iniciada_vida_sexual and total_desenlaces > 0:
            raise ValueError(
                "Incoherencia obstétrica: Una paciente que no ha iniciado vida sexual no puede registrar gestas ni partos."
            )

        if hijos_vivos > (partos + cesareas) and (partos + cesareas) > 0:
            # Observación preventiva (a menos que hayan sido partos múltiples)
            pass

        return self


class AntecedentesUpdate(BaseModel):
    """Actualización parcial de antecedentes médicos con validación de coherencia."""
    iniciada_vida_sexual: Optional[bool] = None
    edad_menarquia: Optional[int] = Field(None, ge=8, le=20)
    tipo_ciclo: Optional[str] = None
    duracion_ciclo_habitual: Optional[int] = Field(None, ge=1, le=90)
    gestas: Optional[int] = Field(None, ge=0)
    partos: Optional[int] = Field(None, ge=0)
    cesareas: Optional[int] = Field(None, ge=0)
    abortos: Optional[int] = Field(None, ge=0)
    hijos_vivos: Optional[int] = Field(None, ge=0)
    usa_anticonceptivos: Optional[bool] = None
    tipo_anticonceptivo: Optional[str] = None
    familiar_con_sop: Optional[bool] = None
    familiar_con_diabetes: Optional[bool] = None
    diabetes: Optional[bool] = None
    hipotiroidismo: Optional[bool] = None
    hiperprolactinemia: Optional[bool] = None
    resistencia_insulina: Optional[bool] = None
    alergias: Optional[str] = None
    observaciones: Optional[str] = None
    historial: Optional[Union[dict, list]] = None

    @field_validator("tipo_ciclo")
    @classmethod
    def validar_tipo_ciclo(cls, v):
        if v is not None and v not in {"regular", "irregular", "amenorrea", "oligomenorrea"}:
            raise ValueError("tipo_ciclo debe ser: regular, irregular, amenorrea u oligomenorrea")
        return v

    @model_validator(mode="after")
    def validar_coherencia_obstetrica(self):
        if self.gestas is not None:
            p = self.partos or 0
            c = self.cesareas or 0
            a = self.abortos or 0
            if (p + c + a) > self.gestas:
                raise ValueError(
                    f"Incoherencia obstétrica: La suma de partos, cesáreas y abortos ({p + c + a}) "
                    f"no puede superar el total de gestas ({self.gestas})."
                )
        return self


class AntecedentesOut(BaseModel):
    """Respuesta completa de antecedentes médicos."""
    id: UUID
    paciente_id: UUID
    iniciada_vida_sexual: bool = False
    edad_menarquia: Optional[int] = None
    tipo_ciclo: Optional[str] = None
    duracion_ciclo_habitual: Optional[int] = None
    gestas: int = 0
    partos: int = 0
    cesareas: int = 0
    abortos: int = 0
    hijos_vivos: int = 0
    usa_anticonceptivos: bool = False
    tipo_anticonceptivo: Optional[str] = None
    familiar_con_sop: bool = False
    familiar_con_diabetes: bool = False
    diabetes: bool = False
    hipotiroidismo: bool = False
    hiperprolactinemia: bool = False
    resistencia_insulina: bool = False
    alergias: Optional[str] = "Ninguna conocida"
    observaciones: Optional[str] = None
    historial: Optional[Union[dict, list]] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def inferir_iniciada_vida_sexual(cls, data):
        if isinstance(data, dict):
            tiene_obs = any(
                (data.get(k) or 0) > 0
                for k in ["gestas", "partos", "cesareas", "abortos", "hijos_vivos"]
            )
            meta_sex = False
            hist = data.get("historial")
            if isinstance(hist, list):
                for h in hist:
                    if isinstance(h, dict) and "__iniciada_vida_sexual__" in h:
                        meta_sex = bool(h["__iniciada_vida_sexual__"])
            elif isinstance(hist, dict):
                meta_sex = bool(hist.get("__iniciada_vida_sexual__", False))

            data["iniciada_vida_sexual"] = bool(
                data.get("iniciada_vida_sexual") or tiene_obs or meta_sex
            )
        return data
