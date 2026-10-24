"""
Esquemas Pydantic para el Registro de Datos Clínicos (HU-010).

Incluye los campos requeridos por el Cuadro 3.10:
Signos de hiperandrogenismo, datos antropométricos y presión arterial.
El score Ferriman-Gallwey debe aceptar únicamente valores entre 0 y 36.
El IMC debe calcularse automáticamente al ingresar peso y talla.
Validaciones hemodinámicas y límites fisiológicos plausibles.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any


class DatosClinicosIn(BaseModel):
    consulta_id: Optional[str] = None
    paciente_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def limpiar_valores_vacios(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if v == "" or v is None or v == "null" or v == "None":
                    cleaned[k] = None
                else:
                    cleaned[k] = v
            return cleaned
        return data

    # Signos físicos de Hiperandrogenismo
    hirsutismo: Optional[bool] = Field(None, description="Presencia clínica de vello terminal anormal")
    score_ferriman_gallwey: Optional[int] = Field(
        None,
        ge=0,
        le=36,
        description="Score Ferriman-Gallwey para hirsutismo (0 a 36)"
    )
    # Desglose de 9 Cuadrantes Ferriman-Gallwey (0 a 4 puntos c/u)
    fg_labio_superior: Optional[int] = Field(None, ge=0, le=4)
    fg_menton: Optional[int] = Field(None, ge=0, le=4)
    fg_pecho: Optional[int] = Field(None, ge=0, le=4)
    fg_abdomen_superior: Optional[int] = Field(None, ge=0, le=4)
    fg_abdomen_inferior: Optional[int] = Field(None, ge=0, le=4)
    fg_brazos: Optional[int] = Field(None, ge=0, le=4)
    fg_muslos: Optional[int] = Field(None, ge=0, le=4)
    fg_espalda_superior: Optional[int] = Field(None, ge=0, le=4)
    fg_espalda_lumbar: Optional[int] = Field(None, ge=0, le=4)
    acne_gags_grado: Optional[int] = Field(None, ge=0, le=4, description="Grado de acné según escala GAGS (0-4)")
    alopecia_ludwig_grado: Optional[int] = Field(None, ge=0, le=3, description="Grado de alopecia según escala Ludwig (0-3)")

    acne: Optional[bool] = Field(None, description="Presencia de acné clínico persistente / severo")
    alopecia_androgenica: Optional[bool] = Field(None, description="Alopecia de patrón androgénico")
    perdida_cabello: Optional[bool] = Field(None, description="Pérdida notoria de cabello")
    acantosis_nigricans: Optional[bool] = Field(None, description="Hiperpigmentación aterciopelada en pliegues cutáneos")
    oscurecimiento_piel: Optional[bool] = Field(None, description="Oscurecimiento cutáneo en cuello o axilas")

    # Ciclo Menstrual
    ciclos_irregulares: Optional[bool] = Field(None, description="Ciclos menstruales irregulares")
    duracion_ciclo_dias: Optional[int] = Field(None, ge=1, le=180, description="Duración habitual del ciclo en días")
    amenorrea: Optional[bool] = Field(None, description="Ausencia de menstruación >90 días")
    oligomenorrea: Optional[bool] = Field(None, description="Intervalos menstruales >35 días")

    # Datos Antropométricos con rangos fisiológicos humanos plausibles
    peso_kg: Optional[float] = Field(None, ge=20.0, le=350.0, description="Peso corporal en kg (20 a 350 kg)")
    talla_cm: Optional[float] = Field(None, ge=80.0, le=250.0, description="Estatura en cm (80 a 250 cm)")
    imc: Optional[float] = Field(None, description="Índice de Masa Corporal")
    circunferencia_abdominal_cm: Optional[float] = Field(None, ge=40.0, le=200.0, description="Circunferencia cintura en cm")
    cadera_cm: Optional[float] = Field(None, ge=50.0, le=220.0, description="Circunferencia cadera en cm")
    relacion_cintura_cadera: Optional[float] = Field(None, description="Relación cintura/cadera")
    ganancia_peso: Optional[bool] = Field(None, description="Aumento de peso reciente")

    # Presión Arterial y Frecuencia Cardíaca
    presion_sistolica: Optional[int] = Field(None, ge=50, le=260, description="Presión arterial sistólica (50-260 mmHg)")
    presion_diastolica: Optional[int] = Field(None, ge=30, le=160, description="Presión arterial diastólica (30-160 mmHg)")
    frecuencia_cardiaca: Optional[int] = Field(None, ge=30, le=250, description="Frecuencia cardíaca (30-250 lpm)")

    # Estado Obstétrico
    embarazada: Optional[bool] = Field(None, description="Estado actual de embarazo")

    @field_validator("score_ferriman_gallwey")
    @classmethod
    def validar_ferriman_gallwey(cls, v):
        if v is not None and (v < 0 or v > 36):
            raise ValueError("El score Ferriman-Gallwey debe aceptar únicamente valores entre 0 y 36.")
        return v

    @model_validator(mode="after")
    def validar_presion_arterial_coherencia(self):
        """Regla hemodinámica: La presión sistólica debe ser estrictamente mayor que la diastólica."""
        sis = self.presion_sistolica
        dia = self.presion_diastolica
        if sis is not None and dia is not None:
            if sis <= dia:
                raise ValueError(
                    f"Incoherencia hemodinámica: La presión arterial sistólica ({sis} mmHg) "
                    f"debe ser mayor a la diastólica ({dia} mmHg)."
                )
        return self


class DatosClinicosOut(DatosClinicosIn):
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    mensaje_confirmacion: Optional[str] = "Datos clínicos guardados exitosamente"
