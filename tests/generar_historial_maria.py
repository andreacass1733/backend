"""
Script para generar el Historial Clínico Completo y Comparativa Evolutiva de María Pérez
═══════════════════════════════════════════════════════════════════════════════════════
Puebla con rigor científico las 3 consultas médicas de María Pérez:
  - Consulta 1 (19/09/2026): Estado Basal (SOP Clásico Completo - Fenotipo A)
  - Consulta 2 (26/09/2026): Control Inicial (Respuesta farmacológica favorable)
  - Consulta 3 (03/10/2026): Control Evolutivo Consolidado (Remisión y normalización)
"""

import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(".env")

from db.supabase_client import get_supabase_admin_client
from services.clinica import tratamiento_service, orden_medica_service, consulta_service

db = get_supabase_admin_client()

MARIA_ID = "94480050-251a-4d92-9ed3-d4f5907ab63c"
C1_ID = "6e9c4322-ab82-4f00-90d9-c5c704b8413f"
C2_ID = "3116aa1f-cd2d-4161-86e7-269f75ad3f43"
C3_ID = "c52b760c-78f9-4f66-ab58-f3f4b22b40d2"


def poblar_historial_maria():
    print(f"Poblando Historial Clínico Integral para María Pérez ({MARIA_ID})...")

    # 1. Asegurar datos personales completos en tabla 'paciente'
    db.table("paciente").update({
        "nombre": "Maria",
        "primer_apellido": "Pérez",
        "segundo_apellido": "Flores",
        "ci": "12174810",
        "fecha_nacimiento": "1998-05-18",
        "telefono": "71234567",
        "email": "maria.perez@paciente.sop.bo"
    }).eq("id", MARIA_ID).execute()
    print("[OK] Datos de identificación de María Pérez actualizados.")

    # 2. Registrar o actualizar antecedentes gineco-obstétricos
    res_ant = db.table("antecedentes_medicos").select("id").eq("paciente_id", MARIA_ID).execute()
    ant_payload = {
        "paciente_id": MARIA_ID,
        "iniciada_vida_sexual": True,
        "edad_menarquia": 12,
        "tipo_ciclo": "oligomenorrea",
        "duracion_ciclo_habitual": 45,
        "gestas": 0,
        "partos": 0,
        "cesareas": 0,
        "abortos": 0,
        "hijos_vivos": 0,
        "usa_anticonceptivos": False,
        "familiar_con_sop": True,
        "familiar_con_diabetes": True,
        "diabetes": False,
        "resistencia_insulina": True,
        "historial": [
            {
                "id": "diag-rotterdam-001",
                "fecha": "2026-09-19T13:00:00Z",
                "tipo_evento": "Diagnóstico Oficial Rotterdam",
                "medico": "Dr. Rodrigo Espinoza",
                "detalle": "Diagnóstico Definitivo: Fenotipo A (SOP Clásico Completo). Cumple 3/3 criterios de Rotterdam: anovulación (oligomenorrea), hiperandrogenismo clínico y bioquímico (Ferriman 14 pts, Testosterona 72 ng/dL) y morfología ecográfica de ovario poliquístico (15 folículos subcapsulares bilateral). Se indica inicio de plan terapéutico multimodal."
            },
            {
                "id": "evol-control-002",
                "fecha": "2026-10-03T15:00:00Z",
                "tipo_evento": "Evaluación Evolutiva Consolidada",
                "medico": "Dr. Rodrigo Espinoza",
                "detalle": "Excelente respuesta terapéutica tras 8 semanas de tratamiento con metformina y antiandrógenos orales. Disminución de IMC de 29.10 a 26.64 kg/m² (-2.46 kg/m²), normalización de relación LH/FSH a 1.48 y HOMA-IR a 2.02. Conteo folicular residual de 2 folículos. Paciente con ciclos regulares de 32 días."
            }
        ]
    }
    if res_ant.data:
        db.table("antecedentes_medicos").update(ant_payload).eq("paciente_id", MARIA_ID).execute()
    else:
        db.table("antecedentes_medicos").insert(ant_payload).execute()
    print("[OK] Antecedentes médicos e historial clínico JSONB configurados.")

    # 3. Actualizar descripciones de las 3 Consultas
    db.table("consulta").update({
        "estado": "completada",
        "motivo": "Evaluación diagnóstica inicial por oligomenorrea, aumento ponderal e hirsutismo",
        "observaciones": "Paciente acude refiriendo retrasos menstruales de 45 a 60 días en los últimos 2 años. Al examen físico se constata sobrepeso (IMC 29.10), hirsutismo moderado (Ferriman-Gallwey 14 pts), acné facial activo y acantosis nigricans cervical. Diagnóstico: Fenotipo A de Rotterdam."
    }).eq("id", C1_ID).execute()

    db.table("consulta").update({
        "estado": "completada",
        "motivo": "Consulta de control y evaluación de respuesta farmacológica inicial",
        "observaciones": "Paciente en tratamiento con metformina 850mg y pauta antiandrogénica. Buena adherencia y tolerancia farmacológica. Se aprecia descenso ponderal inicial (-2.7 kg) y leve mejoría dérmica. Ecografía de control muestra reducción folicular a 6 folículos."
    }).eq("id", C2_ID).execute()

    db.table("consulta").update({
        "estado": "completada",
        "motivo": "Consulta trimestral de evolución clínica, bioquímica y ecográfica",
        "observaciones": "Respuesta terapéutica óptima. Ciclos menstruales regularizados (32 días). Pérdida total acumulada de 6.3 kg de peso corporal (IMC 26.64 kg/m²). Hirsutismo controlado (Ferriman 8 pts). Conteo folicular en rango fisiológico normal (2 folículos). Perfil androgénico e insulínico normalizados."
    }).eq("id", C3_ID).execute()
    print("[OK] Cabeceras de las 3 consultas actualizadas a estado 'completada'.")

    # 4. Poblar Datos Clínicos para las 3 consultas
    # Limpiar previos si existieran para evitar duplicados
    db.table("datos_clinicos").delete().in_("consulta_id", [C1_ID, C2_ID, C3_ID]).execute()

    dc_1 = {
        "consulta_id": C1_ID,
        "peso_kg": 74.5,
        "talla_cm": 160.0,
        "imc": 29.10,
        "circunferencia_abdominal_cm": 88.0,
        "presion_sistolica": 122,
        "presion_diastolica": 78,
        "frecuencia_cardiaca": 76,
        "ciclos_irregulares": True,
        "amenorrea": False,
        "oligomenorrea": True,
        "duracion_ciclo_dias": 50,
        "acne": True,
        "acne_gags_grado": 2,
        "hirsutismo": True,
        "score_ferriman_gallwey": 14,
        "fg_labio_superior": 2,
        "fg_menton": 2,
        "fg_pecho": 1,
        "fg_abdomen_superior": 2,
        "fg_abdomen_inferior": 2,
        "fg_brazos": 1,
        "fg_muslos": 2,
        "fg_espalda_superior": 1,
        "fg_espalda_lumbar": 1,
        "alopecia_androgenica": False,
        "acantosis_nigricans": True,
        "ganancia_peso": True,
        "embarazada": False,
        "created_at": "2026-09-19T12:35:00Z"
    }

    dc_2 = {
        "consulta_id": C2_ID,
        "peso_kg": 71.8,
        "talla_cm": 160.0,
        "imc": 28.05,
        "circunferencia_abdominal_cm": 85.0,
        "presion_sistolica": 118,
        "presion_diastolica": 76,
        "frecuencia_cardiaca": 74,
        "ciclos_irregulares": True,
        "amenorrea": False,
        "oligomenorrea": False,
        "duracion_ciclo_dias": 38,
        "acne": True,
        "acne_gags_grado": 1,
        "hirsutismo": True,
        "score_ferriman_gallwey": 11,
        "fg_labio_superior": 2,
        "fg_menton": 1,
        "fg_pecho": 1,
        "fg_abdomen_superior": 1,
        "fg_abdomen_inferior": 2,
        "fg_brazos": 1,
        "fg_muslos": 1,
        "fg_espalda_superior": 1,
        "fg_espalda_lumbar": 1,
        "alopecia_androgenica": False,
        "acantosis_nigricans": True,
        "ganancia_peso": False,
        "embarazada": False,
        "created_at": "2026-09-26T14:35:00Z"
    }

    dc_3 = {
        "consulta_id": C3_ID,
        "peso_kg": 68.2,
        "talla_cm": 160.0,
        "imc": 26.64,
        "circunferencia_abdominal_cm": 82.0,
        "presion_sistolica": 115,
        "presion_diastolica": 72,
        "frecuencia_cardiaca": 70,
        "ciclos_irregulares": False,
        "amenorrea": False,
        "oligomenorrea": False,
        "duracion_ciclo_dias": 32,
        "acne": False,
        "acne_gags_grado": 0,
        "hirsutismo": False,
        "score_ferriman_gallwey": 8,
        "fg_labio_superior": 1,
        "fg_menton": 1,
        "fg_pecho": 1,
        "fg_abdomen_superior": 1,
        "fg_abdomen_inferior": 1,
        "fg_brazos": 1,
        "fg_muslos": 1,
        "fg_espalda_superior": 0,
        "fg_espalda_lumbar": 1,
        "alopecia_androgenica": False,
        "acantosis_nigricans": False,
        "ganancia_peso": False,
        "embarazada": False,
        "created_at": "2026-10-03T14:45:00Z"
    }

    db.table("datos_clinicos").insert([dc_1, dc_2, dc_3]).execute()
    print("[OK] Datos clínicos para las 3 consultas insertados exitosamente.")

    # 5. Poblar Datos Hormonales para las 3 consultas
    db.table("datos_hormonales").delete().in_("consulta_id", [C1_ID, C2_ID, C3_ID]).execute()

    dh_1 = {
        "consulta_id": C1_ID,
        "lh": 14.8,
        "fsh": 4.9,
        "relacion_lh_fsh": 3.02,
        "testosterona_total": 72.0,
        "dhea_s": 310.0,
        "glucosa_basal": 96.0,
        "insulina_basal": 18.5,
        "homa_ir": 4.38,
        "prolactina": 14.2,
        "tsh": 2.1,
        "amh": 6.8,
        "colesterol_total": 198.0,
        "trigliceridos": 165.0,
        "dia_ciclo_toma": 3,
        "created_at": "2026-09-19T12:40:00Z"
    }

    dh_2 = {
        "consulta_id": C2_ID,
        "lh": 10.2,
        "fsh": 4.8,
        "relacion_lh_fsh": 2.13,
        "testosterona_total": 58.0,
        "dhea_s": 270.0,
        "glucosa_basal": 91.0,
        "insulina_basal": 14.0,
        "homa_ir": 3.15,
        "prolactina": 13.8,
        "tsh": 2.0,
        "amh": 5.4,
        "colesterol_total": 188.0,
        "trigliceridos": 145.0,
        "dia_ciclo_toma": 4,
        "created_at": "2026-09-26T14:40:00Z"
    }

    dh_3 = {
        "consulta_id": C3_ID,
        "lh": 6.8,
        "fsh": 4.6,
        "relacion_lh_fsh": 1.48,
        "testosterona_total": 42.0,
        "dhea_s": 220.0,
        "glucosa_basal": 86.0,
        "insulina_basal": 9.5,
        "homa_ir": 2.02,
        "prolactina": 12.5,
        "tsh": 1.9,
        "amh": 3.8,
        "colesterol_total": 178.0,
        "trigliceridos": 125.0,
        "dia_ciclo_toma": 3,
        "created_at": "2026-10-03T14:50:00Z"
    }

    db.table("datos_hormonales").insert([dh_1, dh_2, dh_3]).execute()
    print("[OK] Datos hormonales para las 3 consultas insertados exitosamente.")

    # 6. Asegurar estudio ecográfico para Consulta 1 (C1_ID)
    res_eco1 = db.table("estudio_ecografico").select("id").eq("consulta_id", C1_ID).execute()
    if not res_eco1.data:
        db.table("estudio_ecografico").insert({
            "consulta_id": C1_ID,
            "num_foliculos": 15,
            "resultado": "Cumple criterio",
            "prob_sop": 0.925,
            "prob_normal": 0.075,
            "validado": True,
            "observacion_medico": "Morfología ecográfica ovárica poliquística clásica con 15 folículos subcapsulares en collar de perlas e hipertrofia estromal central.",
            "created_at": "2026-09-19T12:45:00Z"
        }).execute()
        print("[OK] Estudio ecográfico basal para Consulta 1 registrado (15 folículos).")

    # 7. Registrar Plan de Tratamiento y Prescripciones Farmacológicas
    datos_plan = {
        "tipo": "farmacologico",
        "descripcion": "Terapia Combinada para Sensibilización a la Insulina y Control Hiperandrogénico",
        "objetivo": "Restablecimiento de ciclos ovulatorios regulares, reducción ponderal y control del hirsutismo",
        "duracion_semanas": 24,
        "observaciones": "Control trimestral de tolerancia a la metformina y perfil lipídico. Optimización de ejercicio aeróbico 150 min/semana y dieta hipocalórica.",
        "activo": True
    }
    medicaciones = [
        {
            "nombre_medicamento": "Metformina Clorhidrato",
            "dosis": "850 mg",
            "frecuencia": "Cada 12 horas con las comidas principales",
            "via_administracion": "Oral",
            "fecha_inicio": "2026-09-19",
            "fecha_fin": "2027-03-19",
            "activo": True,
            "indicaciones_especiales": "Tomar inmediatamente después del almuerzo y la cena para minimizar molestias gástricas."
        },
        {
            "nombre_medicamento": "Acetato de Ciproterona + Etinilestradiol",
            "dosis": "2 mg / 0.035 mg",
            "frecuencia": "1 comprimido diario por 21 días consecutivos",
            "via_administracion": "Oral",
            "fecha_inicio": "2026-09-19",
            "fecha_fin": "2027-03-19",
            "activo": True,
            "indicaciones_especiales": "Iniciar en el primer día de la menstruación. Respetar intervalo de 7 días libres de toma."
        },
        {
            "nombre_medicamento": "Mio-Inositol + D-Quiro-Inositol (40:1)",
            "dosis": "2000 mg / 50 mg",
            "frecuencia": "1 sobre diario disuelto en agua",
            "via_administracion": "Oral",
            "fecha_inicio": "2026-09-19",
            "fecha_fin": "2027-03-19",
            "activo": True,
            "indicaciones_especiales": "Consumir por las mañanas antes del desayuno."
        }
    ]
    plan_registrado = tratamiento_service.guardar_plan_tratamiento(MARIA_ID, datos_plan, medicaciones)
    print(f"[OK] Plan de tratamiento y medicaciones registrado exitosamente (ID: {plan_registrado.get('id')}).")

    # 8. Emitir Orden Médica Formal (HU-021) de control semestral
    try:
        from schemas.clinica.orden_medica_schema import OrdenMedicaCreate
        orden_data = OrdenMedicaCreate(
            paciente_id=MARIA_ID,
            consulta_id=C3_ID,
            tipo_ecografia="transvaginal",
            indicacion_ecografia="Control semestral de seguimiento ecográfico ovárico y recuento folicular",
            examenes_laboratorio=[
                {"codigo": "LH", "nombre": "Hormona Luteinizante (LH)", "categoria": "hormonal", "seleccionado": True},
                {"codigo": "FSH", "nombre": "Hormona Folículo Estimulante (FSH)", "categoria": "hormonal", "seleccionado": True},
                {"codigo": "TESTO", "nombre": "Testosterona Total y Libre", "categoria": "hormonal", "seleccionado": True},
                {"codigo": "GLUC_INS", "nombre": "Curva Glucosa e Insulina (HOMA-IR)", "categoria": "metabolico", "seleccionado": True},
                {"codigo": "LIPID", "nombre": "Perfil Lipídico Completo", "categoria": "metabolico", "seleccionado": True}
            ],
            indicaciones_preanaliticas="Ayuno de 8 horas. Extracción preferente entre los días 2do y 4to del ciclo.",
            diagnostico_presuntivo="Seguimiento de Síndrome de Ovario Poliquístico — Fenotipo A en remisión",
            prioridad="normal",
            observaciones="Control post-tratamiento semestral."
        )
        orden_emitida = orden_medica_service.crear_orden_medica(orden_data)
        print(f"[OK] Orden médica emitida exitosamente (ID: {orden_emitida.id}).")
    except Exception as e_ord:
        print("[WARN] Error emitiendo orden médica:", e_ord)

    # 9. Verificar y validar comparativa evolutiva final
    comp = consulta_service.obtener_comparativa_paciente(MARIA_ID)
    print("\n" + "=" * 80)
    print("VERIFICACIÓN EXITOSA DE COMPARATIVA EVOLUTIVA PARA MARÍA PÉREZ:")
    print("=" * 80)
    print(f"Total Consultas Registradas : {comp['total_consultas']}")
    print(f"Comparativa Habilitada     : {comp['habilitada']}")
    print(f"Resumen Clínico Evolutivo  : {comp['resumen_clinico']}")
    print("-" * 80)
    print("DELTAS COMPARATIVOS CALCULADOS:")
    for k, v in comp["deltas"].items():
        if v:
            # Reemplazar flechas unicode para compatibilidad con terminal Windows CP1252
            icono_clean = v.get('icono', '').replace('\u2193', 'v').replace('\u2191', '^').replace('\u2194', '=')
            print(f"  * {k.upper():<14}: Inicial = {v['inicial']} {v['unidad']} | Actual = {v['actual']} {v['unidad']} | Cambio = {v['diferencia']} {v['unidad']} ({v['tendencia']} {icono_clean})")
    print("=" * 80)
    print("HISTORIAL CLINICO DE MARIA PEREZ GENERADO EXITOSAMENTE.")


if __name__ == "__main__":
    poblar_historial_maria()
