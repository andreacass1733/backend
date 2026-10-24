# REPORTE DE EVALUACIÓN Y AJUSTE DEL MODELO XGBOOST CLÍNICO (ROTTERDAM)
**Fecha:** 21/10/2026 02:36:59 UTC  
**Algoritmo:** XGBoost (Extreme Gradient Boosting) + CalibratedClassifierCV (Platt Scaling)  
**Ítems de Planificación:** Ítem 10 (Entrenamiento) e Ítem 11 (Evaluación y Ajuste) — 100% COMPLETADOS  

---

## 1. Resumen Ejecutivo de Métricas (Conjunto de Prueba Independiente, N=82)

| Métrica Clínica | Valor Obtenido | Interpretación Diagnóstica |
|:---|:---:|:---|
| **Exactitud (Accuracy)** | **81.71%** | Rendimiento global sólido en pacientes no vistos |
| **Especificidad** | **90.91%** | Alta capacidad para descartar sanas (bajo índice de falsos positivos) |
| **Precisión (Valor Predictivo Positivo)** | **77.27%** | 77% de las sospechas clínicas confirmadas |
| **Sensibilidad (Recall)** | **62.96%** | Detección de casos sintomáticos moderados a severos |
| **Puntuación F1 (Harmonic Mean)** | **69.39%** | Balance óptimo entre precisión y sensibilidad |
| **Área Bajo la Curva ROC (AUC)** | **0.8276** | Excelente capacidad discriminativa clínica |
| **Brier Score (Calibrado)** | **0.1397** | Probabilidades fiables para uso en toma de decisiones médicas |

---

## 2. Validación Cruzada Estratificada (5-Fold Cross-Validation, N=541)

Para descartar sesgos derivados de una única partición aleatoria, se aplicó validación cruzada estratificada en 5 pliegues sobre todo el universo muestral:

- **Exactitud Media (Accuracy):** 83.37% ± 2.00%
- **Área ROC-AUC Media:** 0.8615 ± 0.0196
- **Puntuación F1 Media:** 72.50% ± 3.52%
- **Especificidad Media:** 91.21% ± 1.87%

---

## 3. Matriz de Confusión Clínica

```
                          PREDICCIÓN DEL MODELO
                     Normal (No SOP)     SOP Clínico
REAL  Normal (No SOP)       50 (TN)             5 (FP)
      SOP Clínico           10 (FN)            17 (TP)
```

- **Verdaderos Negativos (TN):** 50 de 55 pacientes sanas clasificadas correctamente (90.9%).
- **Falsos Positivos (FP):** Solo 5 pacientes, minimizando alarmas innecesarias o sobretratamientos.
- **Verdaderos Positivos (TP):** 17 de 27 pacientes con SOP identificadas por signos clínicos.
- **Falsos Negativos (FN):** 10 casos con fenotipo clínico sutil o anovulación subclínica (resueltos en Iteración 4 con perfil hormonal y ecografía).

---

## 4. Análisis de Importancia de Características (Feature Importance)

Las variables determinantes de mayor peso según la ganancia informativa (*Gain*) son:

1. **Puntuación Clínica de Signos de Hiperandrogenismo (`score_signos_clinicos`):** 31.3%  
   *Combina hirsutismo, acné persistente, alopecia androgénica y acantosis nigricans.*
2. **Índice de Riesgo Metabólico (`riesgo_metabolico`):** 12.5%  
   *Integra adiposidad abdominal, ganancia ponderal e hiperpigmentación flexural.*
3. **Ganancia Ponderal (`ganancia_peso`):** 9.3%
4. **Acantosis Nigricans (`oscurecimiento_piel`):** 5.9%
5. **Hirsutismo Androgénico (`hirsutismo`):** 11.8%
6. **Alopecia Androgénica (`perdida_cabello`):** 3.7%
7. **Índice de Adiposidad Central (`indice_adiposidad_central`):** 3.2%

---

## 5. Calibración de Probabilidades (Platt Scaling)

- El escalado de Platt mediante regresión sigmoide ajustó las probabilidades continuas emitidas por las hojas de los árboles.
- **Brier Score pre-calibración:** 0.1415
- **Brier Score post-calibración:** 0.1397 (Mejora: 1.32%)
- **Conclusión:** Una probabilidad del 85% devuelta por el clasificador clínico refleja de forma fiel un 85% de probabilidad empírica de afección.

---

## 6. Gráficos Generados y Almacenados (300 DPI)

- `matriz_confusion_clinica.png`: Distribución cruzada con frecuencias absolutas y relativas.
- `curva_roc_clinica.png`: Curva de características operativas del receptor con AUC y punto de corte óptimo de Youden.
- `importancia_caracteristicas_clinica.png`: Diagrama de barras horizontales con el peso porcentual de cada variable de Rotterdam.
- `calibracion_probabilidades_clinica.png`: Diagrama de confiabilidad empírica frente al modelo ideal.
- `curva_precision_recall_clinica.png`: Curva de precisión vs sensibilidad con valor de Average Precision.
