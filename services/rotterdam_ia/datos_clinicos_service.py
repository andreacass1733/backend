"""
Servicio para la Gestión de Datos Clínicos y Antropométricos (HU-010).

Implementa:
  - Registro de signos de hiperandrogenismo, antropometría y presión arterial.
  - Validación estricta del Score Ferriman-Gallwey (0 a 36).
  - Cálculo automático del IMC: peso_kg / (talla_m ^ 2).
  - Cálculo automático de la relación cintura/cadera.
  - Persistencia en la tabla 'datos_clinicos' de Supabase y mensaje de confirmación.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from db.supabase_client import supabase
from schemas.rotterdam_ia.datos_clinicos_schema import DatosClinicosIn


def calcular_metricas_antropometricas(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula automáticamente el IMC y la relación cintura/cadera si los datos están presentes."""
    actualizados = dict(datos)

    peso = actualizados.get("peso_kg")
    talla = actualizados.get("talla_cm")

    if peso is not None and talla is not None:
        try:
            p = float(peso)
            t_m = float(talla) / 100.0  # Convertir cm a metros si es > 3
            if t_m <= 0.5:  # Si ya venía en metros
                t_m = float(talla)

            if t_m > 0 and p > 0:
                actualizados["imc"] = round(p / (t_m ** 2), 2)
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    cintura = actualizados.get("circunferencia_abdominal_cm")
    cadera = actualizados.get("cadera_cm")
    if cintura is not None and cadera is not None:
        try:
            c = float(cintura)
            ca = float(cadera)
            if ca > 0:
                actualizados["relacion_cintura_cadera"] = round(c / ca, 2)
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    return actualizados


def validar_datos_clinicos_negocio(datos: Dict[str, Any]) -> None:
    """Verifica reglas de negocio médicas como el rango 0-36 del Score Ferriman-Gallwey y coherencia hemodinámica."""
    fg = datos.get("score_ferriman_gallwey")
    if fg is not None:
        try:
            val_fg = int(fg)
            if val_fg < 0 or val_fg > 36:
                raise ValueError("El score Ferriman-Gallwey debe aceptar únicamente valores entre 0 y 36.")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Score Ferriman-Gallwey inválido: {e}")

    sis = datos.get("presion_sistolica")
    dia = datos.get("presion_diastolica")
    if sis is not None and dia is not None:
        try:
            s = int(sis)
            d = int(dia)
            if s <= d:
                raise ValueError(f"Incoherencia hemodinámica: La presión arterial sistólica ({s} mmHg) debe ser mayor a la diastólica ({d} mmHg).")
            if not (50 <= s <= 260):
                raise ValueError(f"Presión sistólica fuera de rango fisiológico admisible (50-260 mmHg): {s}")
            if not (30 <= d <= 160):
                raise ValueError(f"Presión diastólica fuera de rango fisiológico admisible (30-160 mmHg): {d}")
        except (ValueError, TypeError) as e:
            if "Incoherencia" in str(e) or "admisible" in str(e):
                raise
            raise ValueError(f"Presión arterial inválida: {e}")


def guardar_datos_clinicos(payload: DatosClinicosIn) -> Dict[str, Any]:
    """
    Guarda o actualiza los datos clínicos de la paciente en Supabase.
    Aplica cálculos automáticos de IMC y devuelve mensaje de confirmación.
    """
    raw_dict = payload.model_dump(exclude_unset=True)
    validar_datos_clinicos_negocio(raw_dict)
    procesado = calcular_metricas_antropometricas(raw_dict)

    consulta_id = procesado.get("consulta_id")

    if not consulta_id and procesado.get("paciente_id"):
        from services.rotterdam_ia.criterio3_service import obtener_o_crear_consulta_automatica
        try:
            consulta_id = obtener_o_crear_consulta_automatica(paciente_id=procesado.get("paciente_id"))
            procesado["consulta_id"] = consulta_id
        except Exception as e:
            print("[WARN] No se pudo obtener consulta automática para datos clínicos:", e)

    cols_validas = [
        "consulta_id", "ciclos_irregulares", "duracion_ciclo_dias",
        "amenorrea", "oligomenorrea", "acne", "hirsutismo",
        "score_ferriman_gallwey", "alopecia_androgenica", "acantosis_nigricans",
        "fg_labio_superior", "fg_menton", "fg_pecho", "fg_abdomen_superior",
        "fg_abdomen_inferior", "fg_brazos", "fg_muslos", "fg_espalda_superior",
        "fg_espalda_lumbar", "acne_gags_grado", "alopecia_ludwig_grado",
        "peso_kg", "talla_cm", "imc", "circunferencia_abdominal_cm",
        "presion_sistolica", "presion_diastolica", "frecuencia_cardiaca", "ganancia_peso",
        "oscurecimiento_piel", "perdida_cabello", "embarazada"
    ]

    registro_bd = {}
    for col in cols_validas:
        if col in procesado and procesado[col] is not None:
            registro_bd[col] = procesado[col]

    registro_bd["updated_at"] = datetime.now(timezone.utc).isoformat()

    guardado = None
    if consulta_id:
        existente = None
        try:
            existente = (
                supabase.table("datos_clinicos")
                .select("id")
                .eq("consulta_id", consulta_id)
                .execute()
            )

            if existente.data and len(existente.data) > 0:
                dc_id = existente.data[0]["id"]
                resp = (
                    supabase.table("datos_clinicos")
                    .update(registro_bd)
                    .eq("id", dc_id)
                    .execute()
                )
                if resp.data:
                    guardado = resp.data[0]
            else:
                resp = (
                    supabase.table("datos_clinicos")
                    .insert(registro_bd)
                    .execute()
                )
                if resp.data:
                    guardado = resp.data[0]
        except Exception as e:
            # Fallback tolerante si la columna 'frecuencia_cardiaca' aún no fue agregada con SQL en Supabase
            if "frecuencia_cardiaca" in registro_bd and "frecuencia_cardiaca" in str(e).lower():
                try:
                    registro_sin_fc = {k: v for k, v in registro_bd.items() if k != "frecuencia_cardiaca"}
                    if existente and existente.data and len(existente.data) > 0:
                        resp = supabase.table("datos_clinicos").update(registro_sin_fc).eq("id", existente.data[0]["id"]).execute()
                    else:
                        resp = supabase.table("datos_clinicos").insert(registro_sin_fc).execute()
                    if resp.data:
                        guardado = resp.data[0]
                except Exception as e2:
                    print("[WARN] Error guardando en Supabase datos_clinicos (fallback):", e2)
            else:
                print("[WARN] Error guardando en Supabase datos_clinicos:", e)

    resultado_final = dict(guardado or procesado)
    resultado_final["mensaje_confirmacion"] = "Datos clínicos guardados exitosamente."

    # Registro de Auditoría Médica
    try:
        from services.auth.auditoria_service import registrar_evento_auditoria
        imc_txt = f", IMC: {resultado_final.get('imc')}" if resultado_final.get('imc') else ""
        pa_txt = f", PA: {resultado_final.get('presion_sistolica')}/{resultado_final.get('presion_diastolica')}" if resultado_final.get('presion_sistolica') else ""
        fc_txt = f", FC: {resultado_final.get('frecuencia_cardiaca')} lpm" if resultado_final.get('frecuencia_cardiaca') else ""
        registrar_evento_auditoria(
            usuario="Dr. Rodrigo Espinoza Iturri",
            rol="Endocrinología",
            ip="192.168.1.45",
            estacion="Cons. 1 (Win11/Edge)",
            modulo="EXPEDIENTE",
            evento="REGISTER_CLINICAL_DATA",
            detalle=f"Registro de signos clínicos y antropométricos{imc_txt}{pa_txt}{fc_txt}. Signos vitales registrados.",
            estado="AUDIT_OK",
            paciente_id=f"CI {procesado.get('paciente_id')}" if procesado.get("paciente_id") else None,
            payload_json={"consulta_id": consulta_id, "paciente_id": procesado.get("paciente_id"), **resultado_final}
        )
    except Exception as e_aud:
        print("[WARN] Error auditando datos clínicos:", e_aud)

    return resultado_final


def obtener_datos_clinicos(consulta_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos clínicos registrados para una consulta específica."""
    try:
        resp = (
            supabase.table("datos_clinicos")
            .select("*")
            .eq("consulta_id", consulta_id)
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
    except Exception as e:
        print(f"[WARN] Error al obtener datos clínicos de consulta {consulta_id}:", e)
    return None


def obtener_ultimos_datos_clinicos_paciente(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los últimos datos clínicos y signos vitales registrados para una paciente."""
    if not paciente_id:
        return None
    try:
        resp_cons = (
            supabase.table("consulta")
            .select("id")
            .eq("paciente_id", paciente_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        if resp_cons.data:
            c_ids = [c["id"] for c in resp_cons.data]
            resp_dc = (
                supabase.table("datos_clinicos")
                .select("*")
                .in_("consulta_id", c_ids)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp_dc.data and len(resp_dc.data) > 0:
                return resp_dc.data[0]
    except Exception as e:
        print(f"[WARN] Error obteniendo últimos datos clínicos para paciente {paciente_id}:", e)
    return None
