"""
Router — Plan de Tratamiento y Prescripciones Farmacológicas (HU-016 y HU-017).

Rutas:
    GET  /tratamiento/paciente/{paciente_id}  → Obtener plan y medicamentos
    POST /tratamiento/guardar                 → Guardar o actualizar plan y prescripciones
    POST /tratamiento/medicacion              → Registrar prescripción farmacológica individual
"""

from uuid import UUID
from fastapi import APIRouter, HTTPException
from schemas.clinica.tratamiento_schema import (
    PlanTratamientoIn,
    PlanTratamientoOut,
    MedicacionRegistroRequest,
    MedicacionOut
)
from services.clinica.tratamiento_service import (
    obtener_tratamiento_paciente,
    guardar_plan_tratamiento,
    registrar_medicacion_individual,
)
from services.clinica.paciente_service import obtener_paciente

router = APIRouter(prefix="/tratamiento", tags=["Tratamiento y Farmacologia"])


@router.get("/paciente/{paciente_id}", response_model=PlanTratamientoOut)
def get_tratamiento_paciente(paciente_id: UUID):
    """
    Devuelve el plan de tratamiento y prescripciones médicas del paciente.
    Si no tiene uno creado, retorna un esquema vacío con lista vacía de medicamentos.
    """
    paciente_str = str(paciente_id)
    paciente = obtener_paciente(paciente_str)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    try:
        plan = obtener_tratamiento_paciente(paciente_str)
        if not plan:
            return {
                "id": None,
                "paciente_id": paciente_id,
                "cita_id": None,
                "tipo": "farmacologico",
                "descripcion": "Plan de Tratamiento SOP",
                "objetivo": "Regularización menstrual y control sintomático",
                "duracion_semanas": 24,
                "observaciones": "",
                "activo": True,
                "medicaciones": [],
            }
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/guardar", response_model=PlanTratamientoOut)
def post_guardar_tratamiento(body: PlanTratamientoIn):
    """
    Crea o actualiza el plan terapéutico integral y sus medicamentos asociados.
    Valida la duración en semanas y la coherencia de fechas de cada medicación.
    """
    paciente_str = str(body.paciente_id)
    paciente = obtener_paciente(paciente_str)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    try:
        datos_plan = {
            "cita_id": body.cita_id,
            "tipo": body.tipo,
            "descripcion": body.descripcion,
            "objetivo": body.objetivo,
            "duracion_semanas": body.duracion_semanas,
            "observaciones": body.observaciones,
            "activo": body.activo,
        }
        meds_data = [m.model_dump(mode="json", exclude_none=True) for m in body.medicaciones]
        resultado = guardar_plan_tratamiento(paciente_str, datos_plan, meds_data)
        return resultado
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/medicacion", response_model=MedicacionOut)
def post_registrar_medicacion(body: MedicacionRegistroRequest):
    """
    Registra una prescripción de medicamento vinculada a un tratamiento existente.
    Valida obligatoriamente que la fecha de fin sea posterior a la fecha de inicio.
    """
    try:
        datos = body.model_dump(mode="json")
        return registrar_medicacion_individual(datos)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
