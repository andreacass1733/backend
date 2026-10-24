"""
MÓDULO DE ENTRENAMIENTO XGBOOST CLÍNICO — CRITERIO ROTTERDAM (ÍTEM 10)
═════════════════════════════════════════════════════════════════════════

Este módulo entrena el clasificador XGBoost basado exclusivamente en
variables clínicas y antropométricas según los Criterios de Rotterdam:

Ajustes y Parámetros Técnicos:
  - Árboles (n_estimators): 120 estimadores con tasa de aprendizaje moderada (eta=0.03).
  - Profundidad (max_depth): 3 niveles para capturar interacciones de 2do y 3er orden
    evitando la memorización de ruido muestral.
  - Regularización L1 (reg_alpha = 1.0): Promueve la dispersión (sparsity) eliminando
    coeficientes irrelevantes.
  - Regularización L2 (reg_lambda = 1.5): Suaviza las ponderaciones de las hojas del árbol.
  - Submuestreo estocástico (subsample=0.85, colsample_bytree=0.85).
  - Balanceo de clases en entrenamiento mediante SMOTE.
  - Calibración de probabilidades por escalado de Platt (Sigmoide) para garantizar
    probabilidades clínicas confiables (0% a 100%).
"""

import os
import sys

# Asegurar codificación utf-8 tolerante en stdout/stderr de Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import pandas as pd
import numpy as np
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix, brier_score_loss
)
import joblib


def entrenar_modelo_clinico():
    """Ejecuta el entrenamiento y calibración del XGBoost clínico de Rotterdam."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xgb_base_dir = os.path.dirname(script_dir)
    backend_dir = os.path.abspath(os.path.join(xgb_base_dir, "..", ".."))

    processed_dir = os.path.join(xgb_base_dir, "processed_data")
    models_dir = os.path.join(xgb_base_dir, "models")
    root_models_dir = os.path.join(backend_dir, "models_ia")

    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(root_models_dir, exist_ok=True)

    ruta_train = os.path.join(processed_dir, "train_clinico.csv")
    ruta_val = os.path.join(processed_dir, "val_clinico.csv")
    ruta_test = os.path.join(processed_dir, "test_clinico.csv")

    if not os.path.exists(ruta_train):
        print("[INFO] No se encontraron archivos procesados. Ejecutando preprocesamiento...")
        from preprocesar_xgboost_clinico import preprocesar_datos_clinicos
        preprocesar_datos_clinicos()

    print("[INFO] Cargando conjuntos de datos clínicos...")
    df_train = pd.read_csv(ruta_train)
    df_val = pd.read_csv(ruta_val)
    df_test = pd.read_csv(ruta_test)

    X_train, y_train = df_train.drop(columns=['tiene_sop']), df_train['tiene_sop']
    X_val, y_val = df_val.drop(columns=['tiene_sop']), df_val['tiene_sop']
    X_test, y_test = df_test.drop(columns=['tiene_sop']), df_test['tiene_sop']

    # Balanceo sintético de la clase minoritaria (SOP) en entrenamiento mediante SMOTE
    print(f"[INFO] Aplicando SMOTE sobre Train ({len(X_train)} muestras)...")
    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    print(f"[OK] Muestras post-SMOTE: {len(X_train_res)} (Equilibrio 50/50)")

    # ── CONFIGURACIÓN DEL MODELO XGBOOST CLÍNICO REGULARIZADO ───────────────
    print("\n[INFO] Entrenando XGBClassifier con hiperparámetros optimizados...")
    base_model = xgb.XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=1.0,        # Regularización L1 (Lasso)
        reg_lambda=1.5,       # Regularización L2 (Ridge)
        random_state=42,
        eval_metric='logloss'
    )

    base_model.fit(
        X_train_res,
        y_train_res,
        eval_set=[(X_val, y_val)],
        verbose=False
    )

    # ── CALIBRACIÓN DE PROBABILIDADES (PLATT SCALING / SIGMOID) ───────────────
    print("[INFO] Calibrando probabilidades con CalibratedClassifierCV (Platt Scaling)...")
    calibrated_model = CalibratedClassifierCV(
        estimator=base_model,
        cv='prefit',
        method='sigmoid'
    )
    calibrated_model.fit(X_val, y_val)

    # ── EVALUACIÓN EN CONJUNTO INDEPENDIENTE DE PRUEBA (TEST SET) ────────────
    y_pred_base = base_model.predict(X_test)
    y_prob_base = base_model.predict_proba(X_test)[:, 1]

    y_pred_cal = calibrated_model.predict(X_test)
    y_prob_cal = calibrated_model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred_cal)
    prec = precision_score(y_test, y_pred_cal, zero_division=0)
    rec = recall_score(y_test, y_pred_cal, zero_division=0)
    f1 = f1_score(y_test, y_pred_cal, zero_division=0)
    auc = roc_auc_score(y_test, y_prob_cal)
    brier_base = brier_score_loss(y_test, y_prob_base)
    brier_cal = brier_score_loss(y_test, y_prob_cal)

    cm = confusion_matrix(y_test, y_pred_cal)
    tn, fp, fn, tp = cm.ravel()
    especificidad = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    print("\n" + "=" * 60)
    print("  RESULTADOS CLÍNICOS DEL XGBOOST (TEST SET INDEPENDIENTE)")
    print("=" * 60)
    print(f"  Exactitud Global (Accuracy) : {acc * 100:.2f}%")
    print(f"  Precisión Diagnóstica (PPV)  : {prec * 100:.2f}%")
    print(f"  Sensibilidad Clínica (Recall): {rec * 100:.2f}%")
    print(f"  Especificidad Diagnóstica    : {especificidad * 100:.2f}%")
    print(f"  Puntuación Armónica F1       : {f1 * 100:.2f}%")
    print(f"  Área Bajo la Curva ROC (AUC) : {auc:.4f}")
    print(f"  Brier Score (Calibración)    : {brier_cal:.4f} (Original: {brier_base:.4f})")
    print("=" * 60)
    print("\nMatriz de Confusión Clínica:")
    print(f"  Verdaderos Negativos (TN): {tn:2d} | Falsos Positivos (FP): {fp:2d}")
    print(f"  Falsos Negativos    (FN): {fn:2d} | Verdaderos Positivos (TP): {tp:2d}")
    print("\nReporte Detallado:")
    print(classification_report(y_test, y_pred_cal, target_names=['Normal (No SOP)', 'SOP Clínico']))

    # ── GUARDADO Y SINCRONIZACIÓN DE ARTEFACTOS ──────────────────────────────
    for target_dir in [models_dir, root_models_dir]:
        # Guardar modelo base en JSON y PKL
        base_model.save_model(os.path.join(target_dir, "xgboost_clinico.json"))
        joblib.dump(base_model, os.path.join(target_dir, "xgboost_clinico.pkl"))
        # Guardar modelo calibrado
        joblib.dump(calibrated_model, os.path.join(target_dir, "xgboost_clinico_calibrado.pkl"))

    print(f"[OK] Artefactos clínicos guardados en:")
    print(f"  - {models_dir}")
    print(f"  - {root_models_dir}")

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "specificity": especificidad,
        "f1_score": f1,
        "roc_auc": auc,
        "brier_score": brier_cal,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
    }


if __name__ == "__main__":
    entrenar_modelo_clinico()
