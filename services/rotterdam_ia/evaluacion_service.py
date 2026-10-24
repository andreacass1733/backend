"""
Servicio de Evaluación Clínica y Hormonal mediante XGBoost (HU-013).

Evalúa de forma independiente:
  1. Criterio 1 de Rotterdam: Disfunción Ovulatoria (Oligo/Anovulación).
  2. Criterio 2 de Rotterdam: Hiperandrogenismo Clínico y/o Bioquímico.

Cumple con:
  - Salida independiente para Criterio 1 y Criterio 2 con su respectiva probabilidad (0% a 100%).
  - Manejo de campos faltantes mediante imputación estadística por mediana (imputer_xgboost.pkl).
  - Resumen completo de datos ingresados para verificación médica en pantalla.
  - Manejo controlado de excepciones que reporta errores descriptivos sin tumbar el sistema.
  - Sin contemplar aún la clasificación fenotípica (A, B, C, D) según la indicación del usuario.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

from db.supabase_client import supabase
from schemas.rotterdam_ia.evaluacion_criterios_schema import (
    EvaluacionXGBoostRequest,
    EvaluacionXGBoostResponse,
    DetalleCriterio
)
from services.rotterdam_ia.datos_hormonales_service import (
    obtener_datos_hormonales,
    calcular_calculos_automaticos
)
from services.rotterdam_ia.datos_clinicos_service import (
    obtener_datos_clinicos,
    calcular_metricas_antropometricas
)

# Rutas de artefactos de Machine Learning
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models_ia")
PIPELINE_MODELS_DIR = os.path.join(BASE_DIR, "pipelines", "xgboost", "models")


def _cargar_artefactos_xgboost():
    """Carga los transformadores e inferenciador de XGBoost con fallback seguro."""
    rutas_a_probar = [os.path.join(MODELS_DIR, "xgboost"), MODELS_DIR, PIPELINE_MODELS_DIR]

    scaler = None
    imputer = None
    feature_names = None
    model = None

    for m_dir in rutas_a_probar:
        try:
            p_scaler = os.path.join(m_dir, "scaler_xgboost.pkl")
            p_imputer = os.path.join(m_dir, "imputer_xgboost.pkl")
            p_features = os.path.join(m_dir, "feature_names.pkl")
            p_model = os.path.join(m_dir, "best_xgboost.pkl")

            if os.path.exists(p_scaler) and os.path.exists(p_imputer) and os.path.exists(p_model):
                scaler = joblib.load(p_scaler)
                imputer = joblib.load(p_imputer)
                feature_names = joblib.load(p_features)
                model = joblib.load(p_model)
                break
        except Exception as e:
            print(f"[WARN] Error cargando artefactos desde {m_dir}: {e}")

    if not model or not scaler or not imputer:
        raise RuntimeError("No se pudieron cargar los modelos y artefactos de XGBoost.")

    return model, scaler, imputer, feature_names


def _cargar_artefactos_xgboost_clinico():
    """Carga los transformadores y el modelo XGBoost clínico calibrado de Rotterdam (Ítems 10 y 11)."""
    rutas_a_probar = [os.path.join(MODELS_DIR, "xgboost"), MODELS_DIR, PIPELINE_MODELS_DIR]

    scaler = None
    imputer = None
    feature_names = None
    model = None

    for m_dir in rutas_a_probar:
        try:
            p_scaler = os.path.join(m_dir, "scaler_clinico.pkl")
            p_imputer = os.path.join(m_dir, "imputer_clinico.pkl")
            p_features = os.path.join(m_dir, "feature_names_clinico.pkl")
            p_model = os.path.join(m_dir, "xgboost_clinico_calibrado.pkl")
            if not os.path.exists(p_model):
                p_model = os.path.join(m_dir, "xgboost_clinico.pkl")

            if os.path.exists(p_scaler) and os.path.exists(p_imputer) and os.path.exists(p_model):
                scaler = joblib.load(p_scaler)
                imputer = joblib.load(p_imputer)
                feature_names = joblib.load(p_features)
                model = joblib.load(p_model)
                break
        except Exception as e:
            print(f"[WARN] Error cargando artefactos clínicos desde {m_dir}: {e}")

    return model, scaler, imputer, feature_names


def inferir_probabilidad_clinica_xgboost(clinicos: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula la probabilidad calibrada mediante el modelo XGBoost clínico de Rotterdam
    (entrenado sobre variables clínicas, somatométricas e hiperandrogenismo cutáneo).
    """
    try:
        model, scaler, imputer, feature_names = _cargar_artefactos_xgboost_clinico()
        if not model or not scaler or not imputer or not feature_names:
            return 0.50, {"status": "Modelo clínico no disponible"}

        row = {}
        for feat in ['presion_sistolica', 'presion_diastolica', 'cadera_cm', 'cintura_cm', 'relacion_cintura_cadera']:
            v = clinicos.get(feat)
            try:
                row[feat] = float(v) if v is not None else np.nan
            except (ValueError, TypeError):
                row[feat] = np.nan

        if np.isnan(row.get('cintura_cm', np.nan)) and clinicos.get('circunferencia_abdominal_cm') is not None:
            try:
                row['cintura_cm'] = float(clinicos['circunferencia_abdominal_cm'])
            except:
                pass

        def _b(v):
            if v is None:
                return np.nan
            if isinstance(v, bool):
                return 1.0 if v else 0.0
            s = str(v).strip().lower()
            return 1.0 if s in ['1', 'true', 'si', 'sí', 's'] else 0.0

        for feat in ['hirsutismo', 'perdida_cabello', 'acne', 'oscurecimiento_piel', 'ganancia_peso', 'embarazada']:
            v = clinicos.get(feat)
            if feat == 'hirsutismo' and clinicos.get('score_ferriman_gallwey') is not None:
                try:
                    if int(clinicos['score_ferriman_gallwey']) >= 8:
                        v = True
                except:
                    pass
            if feat == 'perdida_cabello' and v is None:
                v = clinicos.get('alopecia_androgenica')
            if feat == 'oscurecimiento_piel' and v is None:
                v = clinicos.get('acantosis_nigricans')
            row[feat] = _b(v)

        # Variables derivadas de Rotterdam
        hirs = row.get('hirsutismo') or 0.0
        acn = row.get('acne') or 0.0
        alo = row.get('perdida_cabello') or 0.0
        osc = row.get('oscurecimiento_piel') or 0.0
        row['score_signos_clinicos'] = (hirs * 2.0) + (acn * 1.0) + (alo * 1.0) + (osc * 1.5)

        sys_bp = row.get('presion_sistolica') or 110.0
        dia_bp = row.get('presion_diastolica') or 70.0
        row['presion_pulso'] = sys_bp - dia_bp

        cint = row.get('cintura_cm') or 75.0
        cad = row.get('cadera_cm') or 95.0
        row['indice_adiposidad_central'] = cint / (cad + 1e-5)

        rcc = row.get('relacion_cintura_cadera') or 0.80
        peso = row.get('ganancia_peso') or 0.0
        row['riesgo_metabolico'] = (1.0 if rcc > 0.85 else 0.0) + (1.0 if peso == 1.0 else 0.0) + (1.0 if osc == 1.0 else 0.0)

        df_row = pd.DataFrame([[row.get(f, np.nan) for f in feature_names]], columns=feature_names)
        df_imp = imputer.transform(df_row)
        df_sc = scaler.transform(df_imp)
        prob = float(model.predict_proba(df_sc)[0, 1])
        return prob, {"status": "Inferencia clínica XGBoost exitosa", "probabilidad": prob}
    except Exception as e:
        print("[WARN] Error en inferir_probabilidad_clinica_xgboost:", e)
        return 0.50, {"status": "Error", "detalle": str(e)}


def _evaluar_criterio_1_disfuncion_ovulatoria(
    clinicos: Dict[str, Any],
    hormonales: Dict[str, Any]
) -> DetalleCriterio:
    """
    Evalúa el Criterio 1 de Rotterdam: Disfunción ovulatoria (Oligomenorrea / Amenorrea).

    Criterios clínicos de consenso:
      - Amenorrea (ausencia de menstruación >90 días o >3 ciclos consecutivos).
      - Oligomenorrea (intervalos de ciclo >35 días).
      - Ciclos irregulares / impredecibles.
      - Progesterona lútea < 3.0 ng/mL en día ~21-23 del ciclo (anovulación bioquímica).
      - Relación LH/FSH ≥ 2.0 (disregulación gonadotrópica típica).
    """
    factores: List[str] = []
    puntos_sospecha = 0.0

    # 1. Amenorrea franca
    amenorrea = clinicos.get("amenorrea")
    if amenorrea is True:
        factores.append("Amenorrea confirmada (ausencia de menstruación >90 días)")
        puntos_sospecha += 0.85

    # 2. Oligomenorrea o duración >35 días
    oligomenorrea = clinicos.get("oligomenorrea")
    duracion_dias = clinicos.get("duracion_ciclo_dias")
    if oligomenorrea is True:
        factores.append("Oligomenorrea (ciclos espaciados >35 días)")
        puntos_sospecha += 0.70
    elif duracion_dias is not None:
        try:
            d = float(duracion_dias)
            if d > 35:
                factores.append(f"Duración habitual del ciclo prolongada ({int(d)} días > 35 días)")
                puntos_sospecha += 0.75
            elif d < 21:
                factores.append(f"Polimenorrea con ciclos acortados ({int(d)} días < 21 días)")
                puntos_sospecha += 0.50
        except (ValueError, TypeError):
            pass

    # 3. Ciclos irregulares reportados
    ciclos_irregulares = clinicos.get("ciclos_irregulares")
    if ciclos_irregulares is True:
        if not any("Oligomenorrea" in f or "Amenorrea" in f for f in factores):
            factores.append("Ciclos menstruales irregulares e impredecibles")
        puntos_sospecha += 0.60

    # 4. Progesterona en fase lútea anovulatoria
    prog = hormonales.get("progesterona")
    dia_toma = hormonales.get("dia_ciclo_toma")
    if prog is not None:
        try:
            p_val = float(prog)
            if dia_toma and int(dia_toma) >= 18 and int(dia_toma) <= 25:
                if p_val < 3.0:
                    factores.append(f"Progesterona lútea baja ({p_val} ng/mL en día {dia_toma}): anovulación bioquímica")
                    puntos_sospecha += 0.55
                elif p_val >= 5.0:
                    puntos_sospecha = max(0.0, puntos_sospecha - 0.40)
        except (ValueError, TypeError):
            pass

    # 5. Relación LH/FSH ≥ 2.0
    lh_fsh = hormonales.get("relacion_lh_fsh")
    if lh_fsh is not None:
        try:
            ratio = float(lh_fsh)
            if ratio >= 2.0:
                factores.append(f"Relación LH/FSH alterada ({ratio} ≥ 2.0): disregulación gonadotrópica")
                puntos_sospecha += 0.30
        except (ValueError, TypeError):
            pass

    # Cálculo final de probabilidad de disfunción ovulatoria (0 a 100%)
    if amenorrea is True:
        probabilidad = 95.0
    elif oligomenorrea is True or (duracion_dias and float(duracion_dias) > 35):
        probabilidad = min(92.0, 75.0 + (puntos_sospecha * 10.0))
    elif ciclos_irregulares is True:
        probabilidad = min(85.0, 65.0 + (puntos_sospecha * 10.0))
    elif puntos_sospecha > 0:
        probabilidad = min(80.0, 40.0 + (puntos_sospecha * 20.0))
    else:
        # Si no hay signos de disfunción
        probabilidad = 12.5

    cumple = probabilidad >= 50.0

    if not factores:
        if cumple:
            factores.append("Patrón clínico sugestivo de disfunción ovulatoria")
        else:
            factores.append("Ciclos menstruales en frecuencia regular; sin datos de oligo/anovulación")

    resultado = "Cumple criterio" if cumple else "No cumple criterio"
    color = "rojo" if cumple else "verde"
    interpretacion = (
        "Presenta disfunción ovulatoria conforme al consenso de Rotterdam (Oligomenorrea / Anovulación)."
        if cumple else
        "No presenta evidencia clínica ni bioquímica de disfunción ovulatoria (ciclos regulares)."
    )

    return DetalleCriterio(
        nombre="Criterio 1 — Disfunción Ovulatoria (Oligo/Anovulación)",
        cumple=cumple,
        resultado=resultado,
        probabilidad=round(probabilidad, 2),
        indicador_color=color,
        factores_determinantes=factores,
        interpretacion_medica=interpretacion
    )


def _evaluar_criterio_2_hiperandrogenismo(
    clinicos: Dict[str, Any],
    hormonales: Dict[str, Any],
    prob_modelo_xgboost: float
) -> DetalleCriterio:
    """
    Evalúa el Criterio 2 de Rotterdam: Hiperandrogenismo clínico y/o bioquímico.

    Criterios de consenso:
      - Hiperandrogenismo Clínico:
          * Score Ferriman-Gallwey ≥ 8 (hirsutismo clínico).
          * Hirsutismo reportado positivo.
          * Acné clínico persistente o severo.
          * Alopecia androgénica (patrón Ludwig o adelgazamiento parietal).
          * Acantosis nigricans (resistencia androgénica/insulínica).
      - Hiperandrogenismo Bioquímico:
          * Testosterona total > 50 ng/dL.
          * DHEA-S > 350 µg/dL.
          * Androstenediona > 2.7 ng/mL.
          * 17-OH-Progesterona elevada.
      - Clasificador XGBoost:
          * Pondera las variables hormonales, somatométricas y metabólicas.
    """
    factores: List[str] = []
    puntos_clinicos = 0.0
    puntos_bioquimicos = 0.0

    # 1. Score Ferriman-Gallwey
    fg = clinicos.get("score_ferriman_gallwey")
    if fg is not None:
        try:
            val_fg = int(fg)
            if val_fg >= 8:
                factores.append(f"Score Ferriman-Gallwey = {val_fg} (≥ 8: Hirsutismo clínico confirmado)")
                puntos_clinicos += 0.85
            elif val_fg > 0:
                factores.append(f"Score Ferriman-Gallwey = {val_fg} (leve o sub-clínico)")
        except (ValueError, TypeError):
            pass

    # 2. Hirsutismo clínico binario
    hirsutismo = clinicos.get("hirsutismo")
    if hirsutismo is True and not any("Ferriman-Gallwey" in f and "≥ 8" in f for f in factores):
        factores.append("Hirsutismo clínico positivo")
        puntos_clinicos += 0.75

    # 3. Acné persistente
    acne = clinicos.get("acne")
    if acne is True:
        factores.append("Acné clínico persistente")
        puntos_clinicos += 0.35

    # 4. Alopecia androgénica / pérdida de cabello
    alopecia = clinicos.get("alopecia_androgenica") or clinicos.get("perdida_cabello")
    if alopecia is True:
        factores.append("Alopecia de distribución androgénica")
        puntos_clinicos += 0.40

    # 5. Acantosis nigricans
    acantosis = clinicos.get("acantosis_nigricans") or clinicos.get("oscurecimiento_piel")
    if acantosis is True:
        factores.append("Acantosis nigricans (marcador físico de hiperinsulinemia/hiperandrogenismo)")
        puntos_clinicos += 0.35

    # 6. Testosterona total
    testo = hormonales.get("testosterona_total")
    if testo is not None:
        try:
            t = float(testo)
            if t > 50.0:
                factores.append(f"Testosterona total elevada ({t} ng/dL > 50 ng/dL): hiperandrogenismo bioquímico")
                puntos_bioquimicos += 0.85
        except (ValueError, TypeError):
            pass

    # 7. DHEA-S
    dhea = hormonales.get("dhea_s")
    if dhea is not None:
        try:
            dh = float(dhea)
            if dh > 350.0:
                factores.append(f"DHEA-S elevado ({dh} µg/dL > 350 µg/dL): exceso androgénico suprarrenal")
                puntos_bioquimicos += 0.70
        except (ValueError, TypeError):
            pass

    # 8. Androstenediona
    andro = hormonales.get("androstenediona")
    if andro is not None:
        try:
            an = float(andro)
            if an > 2.7:
                factores.append(f"Androstenediona elevada ({an} ng/mL > 2.7 ng/mL)")
                puntos_bioquimicos += 0.60
        except (ValueError, TypeError):
            pass

    # 9. 17-OH-Progesterona
    ohp = hormonales.get("hidroxiprogesterona_17")
    if ohp is not None:
        try:
            o_val = float(ohp)
            if o_val >= 2.0:
                factores.append(f"17-OH-Progesterona elevada ({o_val} ng/mL ≥ 2.0 ng/mL)")
                puntos_bioquimicos += 0.40
        except (ValueError, TypeError):
            pass

    # Combinación equilibrada de regla de consenso y probabilidad de XGBoost
    prob_base = prob_modelo_xgboost * 100.0

    # Si hay confirmación clínica franca (ej. Ferriman-Gallwey >= 8) o bioquímica (Testo > 50):
    if puntos_clinicos >= 0.75 or puntos_bioquimicos >= 0.70:
        probabilidad = max(prob_base, 82.0 + min(16.0, (puntos_clinicos + puntos_bioquimicos) * 5.0))
    elif puntos_clinicos > 0 or puntos_bioquimicos > 0:
        probabilidad = max(prob_base, 55.0 + ((puntos_clinicos + puntos_bioquimicos) * 10.0))
    else:
        probabilidad = min(prob_base, 35.0)

    cumple = probabilidad >= 50.0

    if not factores:
        if cumple:
            factores.append("Perfil hormonal y metabólico compatible con hiperandrogenismo según XGBoost")
        else:
            factores.append("Sin estigmas de hiperandrogenismo clínico ni andrógenos elevados en laboratorio")

    resultado = "Cumple criterio" if cumple else "No cumple criterio"
    color = "rojo" if cumple else "verde"
    interpretacion = (
        "Presenta hiperandrogenismo clínico y/o bioquímico conforme a los criterios de Rotterdam."
        if cumple else
        "No presenta hiperandrogenismo clínico ni bioquímico dentro de los parámetros analizados."
    )

    return DetalleCriterio(
        nombre="Criterio 2 — Hiperandrogenismo Clínico / Bioquímico",
        cumple=cumple,
        resultado=resultado,
        probabilidad=round(probabilidad, 2),
        indicador_color=color,
        factores_determinantes=factores,
        interpretacion_medica=interpretacion
    )


def evaluar_xgboost_criterios_1_y_2(
    payload: EvaluacionXGBoostRequest
) -> EvaluacionXGBoostResponse:
    """
    Ejecuta la evaluación clínica completa mediante XGBoost y reglas de Rotterdam
    para los Criterios 1 y 2 de forma totalmente independiente.
    """
    fecha_actual = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")

    # 1. Recuperar o fusionar datos existentes en BD si se envió consulta_id
    datos_hormonales_dict: Dict[str, Any] = {}
    datos_clinicos_dict: Dict[str, Any] = {}

    if payload.consulta_id:
        prev_horm = obtener_datos_hormonales(payload.consulta_id)
        if prev_horm:
            datos_hormonales_dict.update(prev_horm)

        prev_clin = obtener_datos_clinicos(payload.consulta_id)
        if prev_clin:
            datos_clinicos_dict.update(prev_clin)

    # Sobrescribir con datos directos del payload si se enviaron
    if payload.datos_hormonales:
        datos_hormonales_dict.update(payload.datos_hormonales.model_dump(exclude_unset=True))

    if payload.datos_clinicos:
        datos_clinicos_dict.update(payload.datos_clinicos.model_dump(exclude_unset=True))

    # Aplicar cálculos automáticos (HOMA-IR, LH/FSH, IMC, cintura/cadera)
    datos_hormonales_dict = calcular_calculos_automaticos(datos_hormonales_dict)
    datos_clinicos_dict = calcular_metricas_antropometricas(datos_clinicos_dict)

    # 2. Vectorizar hacia las 26 características esperadas por XGBoost
    # ['presion_sistolica', 'presion_diastolica', 'cadera_cm', 'cintura_cm', 'relacion_cintura_cadera',
    #  'hirsutismo', 'perdida_cabello', 'acne', 'oscurecimiento_piel', 'ganancia_peso', 'embarazada',
    #  'fsh', 'lh', 'tsh', 'amh', 'prolactina', 'progesterona', 'glucosa_basal', 'testosterona_total',
    #  'androstenediona', 'insulina_basal', 'dhea_s', 'colesterol_total', 'ldl', 'hdl', 'trigliceridos']
    
    vector_paciente: Dict[str, Any] = {}

    def _to_float(v):
        if v is None:
            return np.nan
        try:
            return float(v)
        except (ValueError, TypeError):
            return np.nan

    def _to_bool_float(v):
        if v is None:
            return np.nan
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        s = str(v).strip().lower()
        if s in ['1', 'true', 'si', 'sí']:
            return 1.0
        elif s in ['0', 'false', 'no']:
            return 0.0
        return np.nan

    # Signos físicos y antropometría
    vector_paciente['presion_sistolica'] = _to_float(datos_clinicos_dict.get('presion_sistolica'))
    vector_paciente['presion_diastolica'] = _to_float(datos_clinicos_dict.get('presion_diastolica'))
    vector_paciente['cadera_cm'] = _to_float(datos_clinicos_dict.get('cadera_cm'))
    vector_paciente['cintura_cm'] = _to_float(datos_clinicos_dict.get('circunferencia_abdominal_cm'))
    vector_paciente['relacion_cintura_cadera'] = _to_float(datos_clinicos_dict.get('relacion_cintura_cadera'))

    # Si se reportó Ferriman-Gallwey >= 8, se cuenta como hirsutismo positivo
    fg_score = datos_clinicos_dict.get('score_ferriman_gallwey')
    hirsutismo_val = datos_clinicos_dict.get('hirsutismo')
    if fg_score is not None and int(fg_score) >= 8:
        hirsutismo_val = True
    vector_paciente['hirsutismo'] = _to_bool_float(hirsutismo_val)

    # Alopecia / pérdida de cabello
    perdida_cab = datos_clinicos_dict.get('alopecia_androgenica') or datos_clinicos_dict.get('perdida_cabello')
    vector_paciente['perdida_cabello'] = _to_bool_float(perdida_cab)

    vector_paciente['acne'] = _to_bool_float(datos_clinicos_dict.get('acne'))

    # Acantosis nigricans / oscurecimiento de piel
    acantosis_val = datos_clinicos_dict.get('acantosis_nigricans') or datos_clinicos_dict.get('oscurecimiento_piel')
    vector_paciente['oscurecimiento_piel'] = _to_bool_float(acantosis_val)

    vector_paciente['ganancia_peso'] = _to_bool_float(datos_clinicos_dict.get('ganancia_peso'))
    vector_paciente['embarazada'] = _to_bool_float(datos_clinicos_dict.get('embarazada'))

    # Hormonas y laboratorio
    vector_paciente['fsh'] = _to_float(datos_hormonales_dict.get('fsh'))
    vector_paciente['lh'] = _to_float(datos_hormonales_dict.get('lh'))
    vector_paciente['tsh'] = _to_float(datos_hormonales_dict.get('tsh'))
    vector_paciente['amh'] = _to_float(datos_hormonales_dict.get('amh'))
    vector_paciente['prolactina'] = _to_float(datos_hormonales_dict.get('prolactina'))
    vector_paciente['progesterona'] = _to_float(datos_hormonales_dict.get('progesterona'))
    vector_paciente['glucosa_basal'] = _to_float(datos_hormonales_dict.get('glucosa_basal'))
    vector_paciente['testosterona_total'] = _to_float(datos_hormonales_dict.get('testosterona_total'))
    vector_paciente['androstenediona'] = _to_float(datos_hormonales_dict.get('androstenediona'))
    vector_paciente['insulina_basal'] = _to_float(datos_hormonales_dict.get('insulina_basal'))
    vector_paciente['dhea_s'] = _to_float(datos_hormonales_dict.get('dhea_s'))
    vector_paciente['colesterol_total'] = _to_float(datos_hormonales_dict.get('colesterol_total'))
    vector_paciente['ldl'] = _to_float(datos_hormonales_dict.get('ldl'))
    vector_paciente['hdl'] = _to_float(datos_hormonales_dict.get('hdl'))
    vector_paciente['trigliceridos'] = _to_float(datos_hormonales_dict.get('trigliceridos'))

    prob_xgboost = 0.50
    modelo_info = {
        "algoritmo": "XGBoost Classifier Regularizado",
        "arboles": 80,
        "profundidad_maxima": 3,
        "regularizacion": "L1 (reg_alpha=1.5), L2 (reg_lambda=4.0)",
        "imputacion": "SimpleImputer (estrategia de mediana de entrenamiento)",
        "estandarizacion": "StandardScaler (Z-Score)",
        "status": "Inferencia completada con éxito"
    }

    try:
        model, scaler, imputer, feature_names = _cargar_artefactos_xgboost()

        df_row = pd.DataFrame([{col: vector_paciente.get(col, np.nan) for col in feature_names}])

        # Imputar y escalar de forma robusta
        df_imputed = imputer.transform(df_row)
        df_scaled = scaler.transform(df_imputed)

        # Inferencia con probabilidades
        prob_pred = model.predict_proba(df_scaled)[0, 1]
        prob_xgboost = float(prob_pred)
    except Exception as e_model:
        print("[WARN] Error ejecutando modelo XGBoost, aplicando estimación clínica de contingencia:", e_model)
        modelo_info["status"] = f"Aviso: Inferencia asistida por reglas clínicas ({str(e_model)})"

    # 3. Evaluar Criterio 1 y Criterio 2 independientemente
    crit_1 = _evaluar_criterio_1_disfuncion_ovulatoria(datos_clinicos_dict, datos_hormonales_dict)
    crit_2 = _evaluar_criterio_2_hiperandrogenismo(datos_clinicos_dict, datos_hormonales_dict, prob_xgboost)

    # 4. Resumen consolidado de lo que ingresó el médico para verificación en pantalla
    datos_resumen = {
        "hormonales": {k: v for k, v in datos_hormonales_dict.items() if v is not None and k != "semaforo"},
        "clinicos": {k: v for k, v in datos_clinicos_dict.items() if v is not None and k != "mensaje_confirmacion"},
    }

    return EvaluacionXGBoostResponse(
        consulta_id=payload.consulta_id,
        paciente_id=payload.paciente_id,
        fecha_evaluacion=fecha_actual,
        criterio_1=crit_1,
        criterio_2=crit_2,
        datos_ingresados=datos_resumen,
        modelo_info=modelo_info,
        error=False,
        mensaje="Evaluación de Criterios 1 y 2 de Rotterdam completada con éxito."
    )
