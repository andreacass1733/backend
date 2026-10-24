"""
Router de la API para Evaluación mediante XGBoost (HU-013).

Rutas:
  - POST /evaluacion/xgboost: Evalúa Criterio 1 y Criterio 2 de forma independiente.
  - GET  /evaluacion/resumen/{consulta_id}: Obtiene la evaluación completa para una consulta.
"""

from fastapi import APIRouter, HTTPException
from schemas.rotterdam_ia.evaluacion_criterios_schema import (
    EvaluacionXGBoostRequest,
    EvaluacionXGBoostResponse
)
from services.rotterdam_ia.evaluacion_service import evaluar_xgboost_criterios_1_y_2

router = APIRouter(prefix="/evaluacion", tags=["Evaluación XGBoost (HU-013)"])


@router.post("/xgboost", response_model=EvaluacionXGBoostResponse)
def evaluar_con_xgboost(payload: EvaluacionXGBoostRequest):
    """
    Evalúa si la paciente presenta disfunción ovulatoria (Criterio 1)
    e hiperandrogenismo (Criterio 2) a partir de los datos ingresados.
    
    Devuelve:
      - Resultado (cumple / no cumple) para Criterio 1 y Criterio 2 independientemente.
      - Probabilidad calculada para cada criterio (0% a 100%).
      - Soporte para datos incompletos con imputación estadística de medianas.
      - Resumen de datos ingresados para verificación médica en pantalla.
    """
    try:
        resultado = evaluar_xgboost_criterios_1_y_2(payload)
        return resultado
    except Exception as e:
        # En caso de error inesperado, responder con mensaje descriptivo sin romper la API
        print("[ERROR] Fallo en evaluación XGBoost:", e)
        from datetime import datetime, timezone
        from schemas.rotterdam_ia.evaluacion_criterios_schema import DetalleCriterio
        return EvaluacionXGBoostResponse(
            consulta_id=payload.consulta_id,
            paciente_id=payload.paciente_id,
            fecha_evaluacion=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC"),
            criterio_1=DetalleCriterio(
                nombre="Criterio 1 — Disfunción Ovulatoria",
                cumple=False,
                resultado="No evaluable",
                probabilidad=0.0,
                indicador_color="gris",
                factores_determinantes=["Error durante el procesamiento del Criterio 1."],
                interpretacion_medica="No se pudo procesar la evaluación ovulatoria."
            ),
            criterio_2=DetalleCriterio(
                nombre="Criterio 2 — Hiperandrogenismo",
                cumple=False,
                resultado="No evaluable",
                probabilidad=0.0,
                indicador_color="gris",
                factores_determinantes=["Error durante la inferencia de XGBoost."],
                interpretacion_medica="No se pudo procesar la evaluación de hiperandrogenismo."
            ),
            datos_ingresados={},
            modelo_info={"status": "Error", "detalle": str(e)},
            error=True,
            mensaje=f"Aviso médico: Ocurrió un error en el motor de evaluación ({str(e)}). Por favor verifique los datos ingresados."
        )


@router.get("/consulta/{consulta_id}", response_model=EvaluacionXGBoostResponse)
def evaluar_consulta_existente(consulta_id: str):
    """Evalúa los datos clínicos y hormonales ya registrados en Supabase para una consulta."""
    req = EvaluacionXGBoostRequest(consulta_id=consulta_id)
    return evaluar_con_xgboost(req)


@router.get("/metricas-clinicas")
def obtener_metricas_xgboost_clinico():
    """
    Retorna las métricas científicas, validación y parámetros del clasificador
    XGBoost clínico de Rotterdam (Ítems 10 y 11 de la Planificación).
    """
    import os
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    posibles_rutas = [
        os.path.join(base_dir, 'models_ia', 'xgboost', 'metricas_clinicas.json'),
        os.path.join(base_dir, "outputs", "evaluacion_clinica", "metricas_clinicas.json"),
        os.path.join(base_dir, "pipelines", "xgboost", "evaluacion_clinica", "metricas_clinicas.json")
    ]
    for r in posibles_rutas:
        if os.path.exists(r):
            with open(r, "r", encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(status_code=404, detail="Métricas de evaluación clínica no encontradas.")
