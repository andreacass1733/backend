"""
Servicio de Clasificación Fenotípica de Rotterdam y Cálculos Automáticos Hormonales/Clínicos.

Implementa los Requerimientos Funcionales:
  - RF-11: Cálculo automático de HOMA-IR ((glucosa * insulina) / 405) y relación LH/FSH (lh / fsh)
  - RF-13: Cálculo automático de IMC (peso / talla^2)
  - RF-20: Clasificación del Fenotipo SOP según la Escala de Rotterdam (A, B, C, D o Sin SOP)
  - RF-21: Visualización de resultados por cada uno de los 3 criterios
"""

from typing import Dict, Any, Optional

def calcular_homa_ir(glucosa_mg_dl: float, insulina_uIU_ml: float) -> float:
    """Calcula el índice HOMA-IR para evaluar resistencia a la insulina."""
    if glucosa_mg_dl <= 0 or insulina_uIU_ml <= 0:
        return 0.0
    return round((glucosa_mg_dl * insulina_uIU_ml) / 405.0, 2)

def calcular_relacion_lh_fsh(lh: float, fsh: float) -> float:
    """Calcula la relación LH/FSH. Un valor > 2.0 sugiere sospecha endocrina de SOP."""
    if fsh <= 0:
        return 0.0
    return round(lh / fsh, 2)

def calcular_imc(peso_kg: float, talla_m: float) -> float:
    """Calcula el Índice de Masa Corporal (IMC)."""
    if talla_m <= 0:
        return 0.0
    return round(peso_kg / (talla_m ** 2), 2)

def clasificar_fenotipo_rotterdam(
    cumple_criterio1: bool,  # Disfunción ovulatoria (Oligo/Amenorrea)
    cumple_criterio2: bool,  # Hiperandrogenismo (Clínico/Bioquímico o XGBoost)
    cumple_criterio3: bool,  # Morfología ecográfica (EfficientNet-B0)
    evaluado_criterio1: bool = True,
    evaluado_criterio2: bool = True,
    evaluado_criterio3: bool = True,
) -> Dict[str, Any]:
    """
    Clasifica el fenotipo de SOP de acuerdo a los consensos internacionales de Rotterdam (2003 / 2023):
    
    Criterios Evaluados:
      - Criterio 1: Oligo/Amenorrea (Disfunción ovulatoria)
      - Criterio 2: Hiperandrogenismo (Clínico/Bioquímico)
      - Criterio 3: Morfología Ecográfica Poliquística (PCOM - EfficientNet-B0)

    Regla Diagnóstica: Requiere al menos 2 de los 3 criterios.

    Manejo de Evaluaciones Incompletas:
      Si faltan estudios y los datos confirmados no alcanzan para emitir un diagnóstico positivo,
      se cataloga como "Evaluación Pendiente" indicando explícitamente cuáles estudios faltan.
    """
    total_criterios = sum([cumple_criterio1, cumple_criterio2, cumple_criterio3])
    tiene_sop = total_criterios >= 2

    fenotipo = "Sin SOP"
    descripcion = "No cumple los criterios mínimos de Rotterdam (se requieren al menos 2 de 3 criterios)."

    if cumple_criterio1 and cumple_criterio2 and cumple_criterio3:
        fenotipo = "Fenotipo A"
        descripcion = "SOP Clásico Completo: Presenta disfunción ovulatoria, hiperandrogenismo y morfología ecográfica de ovario poliquístico (Criterios 1 + 2 + 3)."
    elif cumple_criterio1 and cumple_criterio2 and not cumple_criterio3:
        fenotipo = "Fenotipo B"
        if not evaluado_criterio3:
            descripcion = "SOP Confirmado — Fenotipo B (Criterios 1 y 2 cumplidos). Pendiente de ecografía ovárica para descartar o ratificar Fenotipo A."
        else:
            descripcion = "SOP Clásico Anovulatorio — Fenotipo B: Presenta disfunción ovulatoria e hiperandrogenismo con ecografía normal o fisiológica."
    elif not cumple_criterio1 and cumple_criterio2 and cumple_criterio3:
        fenotipo = "Fenotipo C"
        descripcion = "SOP Ovulatorio — Fenotipo C: Presenta hiperandrogenismo y morfología ecográfica de ovario poliquístico con ciclos ovulatorios regulares."
    elif cumple_criterio1 and not cumple_criterio2 and cumple_criterio3:
        fenotipo = "Fenotipo D"
        descripcion = "SOP No Hiperandrogénico — Fenotipo D: Presenta disfunción ovulatoria y morfología ecográfica poliquística sin hiperandrogenismo."
    else:
        # Menos de 2 criterios positivos
        todos_evaluados = evaluado_criterio1 and evaluado_criterio2 and evaluado_criterio3
        if not todos_evaluados:
            pendientes = []
            if not evaluado_criterio1: pendientes.append("Criterio 1 (Disfunción Ovulatoria)")
            if not evaluado_criterio2: pendientes.append("Criterio 2 (Hiperandrogenismo Clínico/Bioquímico)")
            if not evaluado_criterio3: pendientes.append("Criterio 3 (Ecografía Ovárica / PCOM)")
            
            fenotipo = "Evaluación Pendiente"
            descripcion = f"Evaluación de Rotterdam incompleta ({total_criterios}/3 criterios positivos confirmados). Faltan estudios: {', '.join(pendientes)} para emitir el dictamen definitivo."
        else:
            fenotipo = "Sin SOP"
            descripcion = "Evaluación médica completa: La paciente no cumple los criterios de Rotterdam para SOP (menos de 2 criterios positivos)."

    return {
        "tiene_sop": tiene_sop,
        "fenotipo": fenotipo,
        "descripcion": descripcion,
        "total_criterios_cumplidos": total_criterios,
        "evaluacion_completa": evaluado_criterio1 and evaluado_criterio2 and evaluado_criterio3,
        "desglose_criterios": {
            "criterio_1_disfuncion_ovulatoria": {
                "cumple": cumple_criterio1,
                "evaluado": evaluado_criterio1,
                "estado": "Cumple criterio" if cumple_criterio1 else ("No cumple criterio" if evaluado_criterio1 else "Evaluación pendiente"),
                "nombre": "Criterio 1 — Disfunción Ovulatoria (Oligomenorrea / Amenorrea)"
            },
            "criterio_2_hiperandrogenismo": {
                "cumple": cumple_criterio2,
                "evaluado": evaluado_criterio2,
                "estado": "Cumple criterio" if cumple_criterio2 else ("No cumple criterio" if evaluado_criterio2 else "Evaluación pendiente"),
                "nombre": "Criterio 2 — Hiperandrogenismo Clínico/Bioquímico (XGBoost)"
            },
            "criterio_3_ecografico": {
                "cumple": cumple_criterio3,
                "evaluado": evaluado_criterio3,
                "estado": "Cumple criterio" if cumple_criterio3 else ("No cumple criterio" if evaluado_criterio3 else "Evaluación pendiente"),
                "nombre": "Criterio 3 — Morfología Ecográfica Poliquística (EfficientNet-B0)"
            }
        }
    }