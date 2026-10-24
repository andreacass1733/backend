"""
Esquemas Pydantic para el Registro de Datos Hormonales (HU-009).

Incluye los 21 campos requeridos por el Cuadro 3.9:
FSH, LH, TSH, AMH, testosterona total, DHEA-S, androstenediona,
17-hidroxiprogesterona, prolactina, progesterona, insulina basal,
glucosa basal, colesterol total, triglicéridos, LDL, HDL, VLDL,
hemoglobina, creatinina, transaminasas y día del ciclo de toma.
Todos opcionales con cálculo automático de HOMA-IR y relación LH/FSH.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any


class DatosHormonalesIn(BaseModel):
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

    @model_validator(mode="after")
    def validar_valores_no_negativos(self):
        for field_name in self.model_fields.keys():
            if field_name in ["consulta_id", "paciente_id", "unidades_referencia"]:
                continue
            val = getattr(self, field_name, None)
            if isinstance(val, (int, float)) and val < 0:
                raise ValueError(f"El parámetro hormonal '{field_name}' no puede ser negativo ({val}).")
        return self

    # Gonadotropinas y Eje Ovárico
    fsh: Optional[float] = Field(None, description="Hormona Folículo Estimulante (mUI/mL)")
    lh: Optional[float] = Field(None, description="Hormona Luteinizante (mUI/mL)")
    tsh: Optional[float] = Field(None, description="Hormona Estimulante de la Tiroides (µUI/mL)")
    amh: Optional[float] = Field(None, description="Hormona Antimülleriana (ng/mL)")

    # Andrógenos
    testosterona_total: Optional[float] = Field(None, description="Testosterona Total (ng/dL)")
    dhea_s: Optional[float] = Field(None, description="Sulfato de Dehidroepiandrosterona (µg/dL)")
    androstenediona: Optional[float] = Field(None, description="Androstenediona (ng/mL)")
    hidroxiprogesterona_17: Optional[float] = Field(None, description="17-Hidroxiprogesterona (ng/mL)")

    # Prolactina y Progesterona
    prolactina: Optional[float] = Field(None, description="Prolactina (ng/mL)")
    progesterona: Optional[float] = Field(None, description="Progesterona (ng/mL)")

    # Metabolismo y Resistencia a la Insulina
    insulina_basal: Optional[float] = Field(None, description="Insulina Basal en ayunas (µUI/mL)")
    glucosa_basal: Optional[float] = Field(None, description="Glucosa Basal en ayunas (mg/dL)")
    homa_ir: Optional[float] = Field(None, description="Índice HOMA-IR (calculado automáticamente)")
    relacion_lh_fsh: Optional[float] = Field(None, description="Relación LH/FSH (calculada automáticamente)")
    # Curva Dinámica CTOG (75g)
    glucosa_60: Optional[float] = Field(None, description="Glucemia a los 60 min (mg/dL)")
    glucosa_120: Optional[float] = Field(None, description="Glucemia a los 120 min (mg/dL)")
    insulina_60: Optional[float] = Field(None, description="Insulinemia a los 60 min (µUI/mL)")
    insulina_120: Optional[float] = Field(None, description="Insulinemia a los 120 min (µUI/mL)")
    indice_quicki: Optional[float] = Field(None, description="Índice QUICKI de sensibilidad a la insulina")
    indice_matsuda: Optional[float] = Field(None, description="Índice Matsuda Composite ISI (0-120 min)")

    # Perfil Lipídico
    colesterol_total: Optional[float] = Field(None, description="Colesterol Total (mg/dL)")
    trigliceridos: Optional[float] = Field(None, description="Triglicéridos (mg/dL)")
    ldl: Optional[float] = Field(None, description="Colesterol LDL (mg/dL)")
    hdl: Optional[float] = Field(None, description="Colesterol HDL (mg/dL)")
    vldl: Optional[float] = Field(None, description="Colesterol VLDL (mg/dL)")

    # Hematología y Función Renal/Hepática
    hemoglobina: Optional[float] = Field(None, description="Hemoglobina (g/dL)")
    creatinina: Optional[float] = Field(None, description="Creatinina sérica (mg/dL)")
    transaminasas: Optional[float] = Field(None, description="Transaminasas GOT/GPT (U/L)")

    # Metadatos clínicos de toma
    dia_ciclo_toma: Optional[int] = Field(None, ge=1, le=35, description="Día del ciclo menstrual al tomar la muestra (1 a 35)")
    unidades_referencia: Optional[str] = Field(None, description="Notas de unidades de laboratorio")


class SemaforoItem(BaseModel):
    valor: Optional[float]
    estado: str  # "normal" | "alterado" | "no_ingresado"
    rango_referencia: str
    unidad: str
    interpretacion: str


class DatosHormonalesOut(DatosHormonalesIn):
    id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    semaforo: Optional[Dict[str, SemaforoItem]] = None
