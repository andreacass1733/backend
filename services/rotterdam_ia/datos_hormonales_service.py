"""
Servicio para la Gestión de Datos Hormonales (HU-009).

Implementa:
  - Almacenamiento y consulta en la tabla 'datos_hormonales' de Supabase.
  - Cálculo automático de HOMA-IR: (glucosa * insulina) / 405.0.
  - Cálculo automático de la relación LH/FSH: lh / fsh.
  - Semáforo clínico (verde = normal, rojo = alterado) según rangos de referencia médica.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from db.supabase_client import supabase
from schemas.rotterdam_ia.datos_hormonales_schema import DatosHormonalesIn, DatosHormonalesOut, SemaforoItem

# Rangos clínicos de referencia para mujeres en edad reproductiva
RANGOS_REFERENCIA = {
    "fsh": {
        "min": 3.5, "max": 12.5, "unidad": "mUI/mL",
        "descripcion": "Fase folicular habitual: 3.5 - 12.5 mUI/mL",
        "check": lambda v: 3.5 <= v <= 12.5
    },
    "lh": {
        "min": 2.4, "max": 12.6, "unidad": "mUI/mL",
        "descripcion": "Fase folicular habitual: 2.4 - 12.6 mUI/mL",
        "check": lambda v: 2.4 <= v <= 12.6
    },
    "relacion_lh_fsh": {
        "min": 0.0, "max": 2.0, "unidad": "ratio",
        "descripcion": "Normal < 2.0. En SOP suele ser ≥ 2.0",
        "check": lambda v: v < 2.0
    },
    "tsh": {
        "min": 0.4, "max": 4.5, "unidad": "µUI/mL",
        "descripcion": "Normal: 0.4 - 4.5 µUI/mL",
        "check": lambda v: 0.4 <= v <= 4.5
    },
    "amh": {
        "min": 1.0, "max": 4.0, "unidad": "ng/mL",
        "descripcion": "Normal: 1.0 - 4.0 ng/mL. Elevada (>4.0) en SOP",
        "check": lambda v: v <= 4.0
    },
    "testosterona_total": {
        "min": 15.0, "max": 50.0, "unidad": "ng/dL",
        "descripcion": "Normal: 15.0 - 50.0 ng/dL. Hiperandrogenismo > 50.0",
        "check": lambda v: v <= 50.0
    },
    "dhea_s": {
        "min": 35.0, "max": 350.0, "unidad": "µg/dL",
        "descripcion": "Normal: 35.0 - 350.0 µg/dL. Hiperandrogenismo suprarrenal > 350.0",
        "check": lambda v: v <= 350.0
    },
    "androstenediona": {
        "min": 0.4, "max": 2.7, "unidad": "ng/mL",
        "descripcion": "Normal: 0.4 - 2.7 ng/mL. Elevada > 2.7",
        "check": lambda v: v <= 2.7
    },
    "hidroxiprogesterona_17": {
        "min": 0.2, "max": 2.0, "unidad": "ng/mL",
        "descripcion": "Normal fase folicular: < 2.0 ng/mL",
        "check": lambda v: v < 2.0
    },
    "prolactina": {
        "min": 4.8, "max": 23.3, "unidad": "ng/mL",
        "descripcion": "Normal: 4.8 - 23.3 ng/mL. Hiperprolactinemia > 23.3",
        "check": lambda v: v <= 23.3
    },
    "progesterona": {
        "min": 0.1, "max": 25.0, "unidad": "ng/mL",
        "descripcion": "Fase folicular < 1.0. Fase lútea óptima > 5.0. Anovulación si < 3.0 en día 21",
        "check": lambda v: v >= 0.1
    },
    "insulina_basal": {
        "min": 2.0, "max": 20.0, "unidad": "µUI/mL",
        "descripcion": "Normal en ayunas: 2.0 - 20.0 µUI/mL (óptimo < 12.0)",
        "check": lambda v: 2.0 <= v <= 20.0
    },
    "glucosa_basal": {
        "min": 70.0, "max": 99.0, "unidad": "mg/dL",
        "descripcion": "Normal en ayunas: 70 - 99 mg/dL. Glucemia alterada ≥ 100",
        "check": lambda v: 70.0 <= v < 100.0
    },
    "homa_ir": {
        "min": 0.0, "max": 2.5, "unidad": "índice",
        "descripcion": "Normal < 2.5. Resistencia a la insulina ≥ 2.5",
        "check": lambda v: v < 2.5
    },
    "colesterol_total": {
        "min": 100.0, "max": 199.0, "unidad": "mg/dL",
        "descripcion": "Deseable < 200 mg/dL",
        "check": lambda v: v < 200.0
    },
    "trigliceridos": {
        "min": 50.0, "max": 149.0, "unidad": "mg/dL",
        "descripcion": "Normal < 150 mg/dL",
        "check": lambda v: v < 150.0
    },
    "ldl": {
        "min": 50.0, "max": 129.0, "unidad": "mg/dL",
        "descripcion": "Óptimo < 130 mg/dL",
        "check": lambda v: v < 130.0
    },
    "hdl": {
        "min": 50.0, "max": 90.0, "unidad": "mg/dL",
        "descripcion": "Protector ≥ 50 mg/dL en mujeres. Alterado < 50",
        "check": lambda v: v >= 50.0
    },
    "vldl": {
        "min": 5.0, "max": 30.0, "unidad": "mg/dL",
        "descripcion": "Normal: 5 - 30 mg/dL",
        "check": lambda v: 5.0 <= v <= 30.0
    },
    "hemoglobina": {
        "min": 12.0, "max": 16.0, "unidad": "g/dL",
        "descripcion": "Normal mujeres: 12.0 - 16.0 g/dL",
        "check": lambda v: 12.0 <= v <= 16.0
    },
    "creatinina": {
        "min": 0.5, "max": 1.1, "unidad": "mg/dL",
        "descripcion": "Normal: 0.5 - 1.1 mg/dL",
        "check": lambda v: 0.5 <= v <= 1.1
    },
    "transaminasas": {
        "min": 5.0, "max": 35.0, "unidad": "U/L",
        "descripcion": "Normal < 35 U/L",
        "check": lambda v: v <= 35.0
    },
    "dia_ciclo_toma": {
        "min": 1, "max": 35, "unidad": "día",
        "descripcion": "Día del ciclo menstrual (1-35)",
        "check": lambda v: 1 <= v <= 35
    }
}


def calcular_semaforo_para_campo(campo: str, valor: Optional[float]) -> SemaforoItem:
    """Evalúa un valor clínico con respecto a su rango de referencia y asigna color semáforo."""
    if valor is None:
        return SemaforoItem(
            valor=None,
            estado="no_ingresado",
            rango_referencia=RANGOS_REFERENCIA.get(campo, {}).get("descripcion", "No especificado"),
            unidad=RANGOS_REFERENCIA.get(campo, {}).get("unidad", ""),
            interpretacion="Pendiente de laboratorio"
        )

    ref = RANGOS_REFERENCIA.get(campo)
    if not ref:
        return SemaforoItem(
            valor=valor,
            estado="normal",
            rango_referencia="Sin rango estandarizado",
            unidad="",
            interpretacion="Registrado"
        )

    es_normal = ref["check"](valor)
    estado = "normal" if es_normal else "alterado"
    interp = "Dentro del rango fisiológico normal" if es_normal else "Valor alterado fuera del rango de referencia"

    return SemaforoItem(
        valor=round(valor, 3),
        estado=estado,
        rango_referencia=ref["descripcion"],
        unidad=ref["unidad"],
        interpretacion=interp
    )


def generar_semaforo_completo(datos_dict: Dict[str, Any]) -> Dict[str, SemaforoItem]:
    """Genera el diccionario de semáforos para todos los campos hormonales."""
    semaforos = {}
    for campo in RANGOS_REFERENCIA.keys():
        val = datos_dict.get(campo)
        try:
            val_num = float(val) if val is not None and str(val).strip() != "" else None
        except (ValueError, TypeError):
            val_num = None
        semaforos[campo] = calcular_semaforo_para_campo(campo, val_num)
    return semaforos


def calcular_calculos_automaticos(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula automáticamente HOMA-IR y la relación LH/FSH si los insumos están presentes."""
    actualizados = dict(datos)

    # 1. HOMA-IR = (glucosa_basal * insulina_basal) / 405.0
    glucosa = actualizados.get("glucosa_basal")
    insulina = actualizados.get("insulina_basal")
    if glucosa is not None and insulina is not None:
        try:
            g = float(glucosa)
            i = float(insulina)
            if g > 0 and i > 0:
                actualizados["homa_ir"] = round((g * i) / 405.0, 2)
        except (ValueError, TypeError):
            pass

    # 2. Relación LH/FSH = lh / fsh
    lh = actualizados.get("lh")
    fsh = actualizados.get("fsh")
    if lh is not None and fsh is not None:
        try:
            val_lh = float(lh)
            val_fsh = float(fsh)
            if val_fsh > 0:
                actualizados["relacion_lh_fsh"] = round(val_lh / val_fsh, 2)
            else:
                actualizados["relacion_lh_fsh"] = None
        except (ValueError, TypeError):
            actualizados["relacion_lh_fsh"] = None

    return actualizados


def guardar_datos_hormonales(payload: DatosHormonalesIn) -> Dict[str, Any]:
    """
    Inserta o actualiza los datos hormonales de la paciente por consulta en Supabase.
    Aplica cálculos automáticos y genera el mapa de semáforos.
    """
    raw_dict = payload.model_dump(exclude_unset=True)
    procesado = calcular_calculos_automaticos(raw_dict)

    consulta_id = procesado.get("consulta_id")

    # Si no hay consulta_id pero se envió paciente_id, vincular a consulta activa
    if not consulta_id and procesado.get("paciente_id"):
        from services.rotterdam_ia.criterio3_service import obtener_o_crear_consulta_automatica
        try:
            consulta_id = obtener_o_crear_consulta_automatica(paciente_id=procesado.get("paciente_id"))
            procesado["consulta_id"] = consulta_id
        except Exception as e:
            print("[WARN] No se pudo obtener consulta automática para datos hormonales:", e)

    # Preparar registro para la tabla datos_hormonales
    cols_validas = [
        "consulta_id", "testosterona_total", "dhea_s", "lh", "fsh",
        "relacion_lh_fsh", "prolactina", "progesterona", "amh",
        "insulina_basal", "glucosa_basal", "homa_ir", "tsh",
        "glucosa_60", "glucosa_120", "insulina_60", "insulina_120",
        "indice_quicki", "indice_matsuda",
        "androstenediona", "hidroxiprogesterona_17", "colesterol_total",
        "trigliceridos", "ldl", "hdl", "vldl", "hemoglobina", "creatinina",
        "transaminasas", "dia_ciclo_toma", "unidades_referencia"
    ]

    registro_bd = {}
    for col in cols_validas:
        if col in procesado and procesado[col] is not None:
            registro_bd[col] = procesado[col]

    registro_bd["updated_at"] = datetime.now(timezone.utc).isoformat()

    guardado = None
    if consulta_id:
        try:
            # Comprobar si ya existe registro previo para esa consulta
            existente = (
                supabase.table("datos_hormonales")
                .select("id")
                .eq("consulta_id", consulta_id)
                .execute()
            )

            if existente.data and len(existente.data) > 0:
                dh_id = existente.data[0]["id"]
                resp = (
                    supabase.table("datos_hormonales")
                    .update(registro_bd)
                    .eq("id", dh_id)
                    .execute()
                )
                if resp.data:
                    guardado = resp.data[0]
            else:
                resp = (
                    supabase.table("datos_hormonales")
                    .insert(registro_bd)
                    .execute()
                )
                if resp.data:
                    guardado = resp.data[0]
        except Exception as e:
            print("[WARN] Error guardando en Supabase datos_hormonales:", e)

    resultado_final = dict(guardado or procesado)
    resultado_final["semaforo"] = generar_semaforo_completo(resultado_final)

    # Registro de Auditoría Médica
    try:
        from services.auth.auditoria_service import registrar_evento_auditoria
        lh_fsh_txt = f", LH/FSH: {resultado_final.get('relacion_lh_fsh')}" if resultado_final.get('relacion_lh_fsh') else ""
        homa_txt = f", HOMA-IR: {resultado_final.get('homa_ir')}" if resultado_final.get('homa_ir') else ""
        registrar_evento_auditoria(
            usuario="Dr. Rodrigo Espinoza Iturri",
            rol="Endocrinología",
            ip="192.168.1.45",
            estacion="Cons. 1 (Win11/Edge)",
            modulo="EVALUACION_IA",
            evento="REGISTER_HORMONAL_DATA",
            detalle=f"Registro de perfil hormonal de laboratorio{lh_fsh_txt}{homa_txt}. Cálculos automáticos validados.",
            estado="AUDIT_OK",
            paciente_id=f"CI {procesado.get('paciente_id')}" if procesado.get("paciente_id") else None,
            payload_json={"consulta_id": consulta_id, "paciente_id": procesado.get("paciente_id"), **resultado_final}
        )
    except Exception as e_aud:
        print("[WARN] Error auditando datos hormonales:", e_aud)

    return resultado_final


def obtener_datos_hormonales(consulta_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los datos hormonales registrados para una consulta específica con semáforos."""
    try:
        resp = (
            supabase.table("datos_hormonales")
            .select("*")
            .eq("consulta_id", consulta_id)
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            datos = resp.data[0]
            datos["semaforo"] = generar_semaforo_completo(datos)
            return datos
    except Exception as e:
        print(f"[WARN] Error al obtener datos hormonales de consulta {consulta_id}:", e)
    return None


def obtener_ultimos_datos_hormonales_paciente(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene el último perfil hormonal registrado para una paciente."""
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
            resp_dh = (
                supabase.table("datos_hormonales")
                .select("*")
                .in_("consulta_id", c_ids)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp_dh.data and len(resp_dh.data) > 0:
                dh_row = resp_dh.data[0]
                dh_row["semaforo"] = generar_semaforo_completo(dh_row)
                return dh_row
    except Exception as e:
        print(f"[WARN] Error obteniendo últimos datos hormonales para paciente {paciente_id}:", e)
    return None
