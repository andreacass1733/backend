"""
MÓDULO DE PREPROCESAMIENTO CLÍNICO PARA XGBOOST (CRITERIO ROTTERDAM)
═════════════════════════════════════════════════════════════════════

Este módulo implementa el tratamiento de datos y preparación de variables
para el clasificador clínico de Síndrome de Ovario Poliquístico (SOP)
según el Consenso de Rotterdam (Ítem 10 de la Planificación):

Etapas implementadas:
  1. Carga de dataset clínico crudo (`raw_data/dataset_clinico_limpio.xlsx`).
  2. Limpieza de nombres de columna y mapeo binario robusto de variables cualitativas.
  3. Tratamiento fisiológico de anomalías y acotamiento de valores atípicos (IQR Clipping).
  4. Ingeniería de características clínicas de Rotterdam:
     - Score ponderado de signos clínicos de hiperandrogenismo cutáneo/piloso.
     - Presión de pulso arterial (marcador de rigidez hemodinámica).
     - Relación e índice de adiposidad central y riesgo metabólico.
  5. Imputación estadística por mediana de atributos (`SimpleImputer`).
  6. Estandarización Z-score de variables continuas (`StandardScaler`).
  7. División estratificada (70% Train, 15% Validación, 15% Test).
  8. Serialización de transformadores y guardado de CSVs procesados.
"""

import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import joblib


def preprocesar_datos_clinicos():
    """Ejecuta el preprocesamiento clínico completo para XGBoost Rotterdam."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xgb_base_dir = os.path.dirname(script_dir)
    backend_dir = os.path.abspath(os.path.join(xgb_base_dir, "..", ".."))

    raw_dir = os.path.join(xgb_base_dir, "raw_data")
    processed_dir = os.path.join(xgb_base_dir, "processed_data")
    models_dir = os.path.join(xgb_base_dir, "models")
    root_models_dir = os.path.join(backend_dir, "models_ia")

    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(root_models_dir, exist_ok=True)

    ruta_clinico = os.path.join(raw_dir, "dataset_clinico_limpio.xlsx")
    if not os.path.exists(ruta_clinico):
        raise FileNotFoundError(f"No se encontró el archivo de datos clínicos en: {ruta_clinico}")

    print("[INFO] Cargando dataset clínico para XGBoost Rotterdam...")
    df = pd.read_excel(ruta_clinico)
    df.columns = df.columns.str.strip().str.lower()

    # Mapeo binario tolerante a variaciones de codificación (UTF-8, ISO, acentos)
    def binary_map(val):
        if pd.isna(val):
            return 0
        s = str(val).strip().lower()
        if s.startswith(('s', 'y', '1', 't')):
            return 1
        elif s.startswith(('n', '0', 'f')):
            return 0
        return 0

    cols_categoricas = [
        'tiene_sop', 'hirsutismo', 'perdida_cabello', 'acne',
        'oscurecimiento_piel', 'ganancia_peso', 'embarazada'
    ]
    for col in cols_categoricas:
        if col in df.columns:
            df[col] = df[col].apply(binary_map)

    # Corrección de anomalías fisiológicas evidentes en registros de presión arterial
    # Presión sistólica inferior a 50 mmHg se ajusta a la mediana normativa (110 mmHg)
    if 'presion_sistolica' in df.columns:
        df.loc[df['presion_sistolica'] < 50, 'presion_sistolica'] = 110.0

    # ── INGENIERÍA DE CARACTERÍSTICAS CLÍNICAS (CONSENSO DE ROTTERDAM) ──────
    # 1. Puntuación compuesta de hiperandrogenismo cutáneo y resistencia insulínica
    df['score_signos_clinicos'] = (
        df['hirsutismo'] * 2.0 +
        df['acne'] * 1.0 +
        df['perdida_cabello'] * 1.0 +
        df['oscurecimiento_piel'] * 1.5
    )

    # 2. Presión de pulso (tensión arterial diferencial)
    df['presion_pulso'] = df['presion_sistolica'] - df['presion_diastolica']

    # 3. Índice de adiposidad central
    df['indice_adiposidad_central'] = df['cintura_cm'] / (df['cadera_cm'] + 1e-5)

    # 4. Índice de riesgo metabólico asociado a SOP
    df['riesgo_metabolico'] = (
        (df['relacion_cintura_cadera'] > 0.85).astype(int) +
        (df['ganancia_peso'] == 1).astype(int) +
        (df['oscurecimiento_piel'] == 1).astype(int)
    )

    # Separar variable objetivo (target) y predictoras (features)
    y = df['tiene_sop'].astype(int)
    X = df.drop(columns=['tiene_sop'])
    feature_names = X.columns.tolist()

    # ── TRATAMIENTO DE OUTLIERS MEDIANTE IQR CLIPPING ────────────────────────
    for col in X.columns:
        if X[col].dtype in [np.float64, np.int64]:
            q1 = X[col].quantile(0.25)
            q3 = X[col].quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                X[col] = np.clip(X[col], lower, upper)

    # ── IMPUTACIÓN Y ESCALADO Z-SCORE ────────────────────────────────────────
    imputer = SimpleImputer(strategy='median')
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    # ── SERIALIZAR TRANSFORMADORES PARA INFERENCIA ───────────────────────────
    for target_dir in [models_dir, root_models_dir]:
        joblib.dump(scaler, os.path.join(target_dir, "scaler_clinico.pkl"))
        joblib.dump(imputer, os.path.join(target_dir, "imputer_clinico.pkl"))
        joblib.dump(feature_names, os.path.join(target_dir, "feature_names_clinico.pkl"))

    print(f"[OK] Artefactos guardados: scaler_clinico.pkl, imputer_clinico.pkl, feature_names_clinico.pkl ({len(feature_names)} variables)")

    # ── DIVISIÓN ESTRATIFICADA (70% Train, 15% Val, 15% Test) ────────────────
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X_scaled, y, test_size=0.15, random_state=42, stratify=y
    )
    val_ratio_adj = 0.15 / 0.85
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=val_ratio_adj, random_state=42, stratify=y_train_val
    )

    # ── EXPORTACIÓN DE DATASETS PROCESADOS ───────────────────────────────────
    df_train = pd.DataFrame(X_train, columns=feature_names)
    df_train['tiene_sop'] = y_train.values
    df_train.to_csv(os.path.join(processed_dir, "train_clinico.csv"), index=False)

    df_val = pd.DataFrame(X_val, columns=feature_names)
    df_val['tiene_sop'] = y_val.values
    df_val.to_csv(os.path.join(processed_dir, "val_clinico.csv"), index=False)

    df_test = pd.DataFrame(X_test, columns=feature_names)
    df_test['tiene_sop'] = y_test.values
    df_test.to_csv(os.path.join(processed_dir, "test_clinico.csv"), index=False)

    df_completo_proc = pd.DataFrame(X_scaled, columns=feature_names)
    df_completo_proc['tiene_sop'] = y.values
    df_completo_proc.to_csv(os.path.join(processed_dir, "dataset_clinico_completo.csv"), index=False)

    print("\n[ÉXITO] Preprocesamiento clínico completado:")
    print(f" - Muestras totales: {len(df)} (SOP: {y.sum()}, Normal: {len(y) - y.sum()})")
    print(f" - Train: {len(df_train)} | Val: {len(df_val)} | Test: {len(df_test)}")
    print(f" - Características: {feature_names}")

    return feature_names, len(df_train), len(df_val), len(df_test)


if __name__ == "__main__":
    preprocesar_datos_clinicos()
