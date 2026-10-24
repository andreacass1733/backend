"""
Servicio del Criterio 2 de Rotterdam: Hiperandrogenismo Clínico y/o Bioquímico.

Evalúa si la paciente cumple el segundo criterio de Rotterdam mediante
el ensamble clasificador XGBoost y las reglas diagnósticas clínicas
(Ferriman-Gallwey, andrógenos en sangre, signos cutáneos y pilosos).
"""

from typing import Dict, Any, Optional
from services.rotterdam_ia.evaluacion_service import (
    _cargar_artefactos_xgboost,
    _evaluar_criterio_2_hiperandrogenismo,
    inferir_probabilidad_clinica_xgboost
)
import numpy as np
import pandas as pd


def run_prediction(datos: dict) -> Dict[str, Any]:
    """
    Ejecuta la evaluación del Criterio 2 a partir de variables clínicas y hormonales.

    Args:
        datos (dict): Contiene variables clínicas ('clinicos') y/o hormonales ('hormonales')
                      o un diccionario plano con los atributos del paciente.

    Returns:
        dict: Resultado con probabilidad, veredicto (Cumple/No cumple) y factores determinantes.
    """
    clinicos = datos.get("clinicos", datos)
    hormonales = datos.get("hormonales", datos)

    prob_xgboost = 0.50
    # Intentar primero inferencia con clasificador clínico específico de Rotterdam (Ítems 10 y 11)
    try:
        prob_clin, info_clin = inferir_probabilidad_clinica_xgboost(clinicos)
        if info_clin.get("status") == "Inferencia clínica XGBoost exitosa":
            prob_xgboost = prob_clin
    except Exception as e_clin:
        print("[WARN] Inferencia clínica XGBoost secundaria:", e_clin)

    try:
        # Si se cuenta con datos hormonales completos, complementar con el ensamble global
        if any(hormonales.get(k) is not None for k in ['testosterona_total', 'fsh', 'lh', 'dhea_s', 'amh']):
            model, scaler, imputer, feature_names = _cargar_artefactos_xgboost()
            row = {}
            for feat in feature_names:
                val = clinicos.get(feat, hormonales.get(feat, np.nan))
                try:
                    row[feat] = float(val) if val is not None else np.nan
                except (ValueError, TypeError):
                    row[feat] = np.nan

            df_row = pd.DataFrame([row])
            df_imputed = imputer.transform(df_row)
            df_scaled = scaler.transform(df_imputed)
            prob_xgboost = float(model.predict_proba(df_scaled)[0, 1])
    except Exception as e:
        print("[WARN] Inferencia XGBoost asistida en Criterio 2:", e)

    resultado = _evaluar_criterio_2_hiperandrogenismo(clinicos, hormonales, prob_xgboost)
    return resultado.model_dump()
