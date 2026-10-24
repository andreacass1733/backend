"""
Servicio para el Plan de Tratamiento y Prescripción de Medicación (HU-016 y HU-017).
Interactúa con las tablas 'tratamiento' y 'medicacion' en Supabase.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from db.supabase_client import get_supabase_admin_client

def _db():
    return get_supabase_admin_client()

TABLA_TRATAMIENTO = "tratamiento"
TABLA_MEDICACION = "medicacion"


def _normalizar_tipo_tratamiento(tipo_raw: Optional[str]) -> str:
    """
    Normaliza el tipo según el constraint 'tratamiento_tipo_check':
    CHECK (tipo IN ('farmacologico', 'quirurgico', 'otro'))
    """
    if not tipo_raw:
        return "farmacologico"
    t = str(tipo_raw).lower()
    if "quirurg" in t:
        return "quirurgico"
    if "otro" in t or "estilo" in t or "combinado" in t:
        return "otro"
    return "farmacologico"


def _obtener_o_crear_cita_paciente(paciente_id: str, ahora: str) -> str:
    """
    Garantiza que exista una cita válida para la paciente.
    Si la paciente acudió sin cita previa solo a buscar o ajustar medicamentos,
    se registra automáticamente la atención médica en la tabla 'cita' con motivo
    'Prescripción de Medicación SOP' y estado 'atendida'.
    """
    hoy_prefix = ahora.split("T")[0]
    try:
        # 1. Verificar si ya existe una cita agendada para el día de hoy
        res_hoy = (
            _db().table("cita")
            .select("id, estado")
            .eq("paciente_id", paciente_id)
            .gte("fecha_atencion", f"{hoy_prefix}T00:00:00")
            .lte("fecha_atencion", f"{hoy_prefix}T23:59:59")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res_hoy.data and len(res_hoy.data) > 0:
            cita_hoy = res_hoy.data[0]
            if cita_hoy.get("estado") != "atendida":
                try:
                    _db().table("cita").update({"estado": "atendida"}).eq("id", cita_hoy["id"]).execute()
                except Exception:
                    pass
            return cita_hoy["id"]
    except Exception as e_hoy:
        print("[WARN] Error buscando cita de hoy:", e_hoy)

    # 2. Si la paciente vino sin cita previa hoy, generar una cita directa de prescripción médica
    try:
        res_med = _db().table("medico").select("id").limit(1).execute()
        med_id = res_med.data[0]["id"] if res_med.data else None

        nueva_cita = (
            _db().table("cita")
            .insert({
                "paciente_id": paciente_id,
                "medico_id": med_id,
                "fecha_atencion": ahora,
                "motivo": "Prescripción de Medicación SOP",
                "observaciones": "Atención médica directa para prescripción y ajuste farmacológico SOP.",
                "estado": "atendida",
                "created_at": ahora,
                "updated_at": ahora,
            })
            .execute()
        )
        if nueva_cita.data and len(nueva_cita.data) > 0:
            return nueva_cita.data[0]["id"]
    except Exception as e_nueva:
        print("[WARN] Error creando cita médica directa para prescripción:", e_nueva)

    # 3. Fallback: Si no se pudo crear, reutilizar la última cita histórica de la paciente
    try:
        res_c = (
            _db().table("cita")
            .select("id")
            .eq("paciente_id", paciente_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res_c.data and len(res_c.data) > 0:
            return res_c.data[0]["id"]
    except Exception as e_fallback:
        print("[WARN] Error buscando cita histórica fallback:", e_fallback)

    raise Exception("No se pudo vincular ni generar una cita médica para el tratamiento")


def obtener_tratamiento_paciente(paciente_id: str) -> Optional[dict]:
    """
    Obtiene el plan de tratamiento activo del paciente y sus medicamentos prescritos.
    """
    # 1. Buscar tratamiento activo
    res_trat = (
        _db().table(TABLA_TRATAMIENTO)
        .select("*")
        .eq("paciente_id", paciente_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not res_trat.data:
        return None

    tratamiento = res_trat.data[0]
    tratamiento_id = tratamiento["id"]

    # 2. Buscar medicamentos asociados
    res_med = (
        _db().table(TABLA_MEDICACION)
        .select("*")
        .eq("tratamiento_id", tratamiento_id)
        .order("created_at", desc=False)
        .execute()
    )

    tratamiento["medicaciones"] = res_med.data or []
    return tratamiento


def guardar_plan_tratamiento(paciente_id: str, datos_plan: dict, medicaciones: list) -> dict:
    """
    Crea o actualiza el plan de tratamiento para el paciente y sincroniza sus medicamentos en Supabase.
    """
    ahora = datetime.now(timezone.utc).isoformat()

    # 1. Resolver cita requerida por la base de datos
    cita_id = datos_plan.get("cita_id")
    if not cita_id:
        cita_id = _obtener_o_crear_cita_paciente(paciente_id, ahora)
    else:
        cita_id = str(cita_id)

    tipo_val = _normalizar_tipo_tratamiento(datos_plan.get("tipo"))
    desc_val = datos_plan.get("descripcion") or "Plan Terapéutico y Farmacológico SOP"
    obj_val = datos_plan.get("objetivo") or "Regulación ovulatoria y control hiperandrogénico"
    dur_semanas = int(datos_plan.get("duracion_semanas") or 24)

    # 2. Validar coherencia de fechas en medicaciones antes de tocar la base de datos
    if medicaciones and len(medicaciones) > 0:
        for m in medicaciones:
            f_ini = m.get("fecha_inicio")
            f_fin = m.get("fecha_fin")
            if f_ini and f_fin and str(f_fin) <= str(f_ini):
                raise ValueError("La fecha de fin de la medicación debe ser estrictamente posterior a la fecha de inicio.")

    # 3. Verificar si ya existe tratamiento para este paciente
    existente = (
        _db().table(TABLA_TRATAMIENTO)
        .select("id")
        .eq("paciente_id", paciente_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    campos_tratamiento = {
        "paciente_id": paciente_id,
        "cita_id": cita_id,
        "tipo": tipo_val,
        "descripcion": desc_val,
        "objetivo": obj_val,
        "duracion_semanas": dur_semanas,
        "observaciones": datos_plan.get("observaciones") or "",
        "activo": datos_plan.get("activo", True),
        "updated_at": ahora,
    }

    if existente.data and len(existente.data) > 0:
        tratamiento_id = existente.data[0]["id"]
        _db().table(TABLA_TRATAMIENTO).update(campos_tratamiento).eq("id", tratamiento_id).execute()
    else:
        campos_tratamiento["created_at"] = ahora
        res_ins = _db().table(TABLA_TRATAMIENTO).insert(campos_tratamiento).execute()
        if not res_ins.data:
            raise Exception("No se pudo crear el registro de tratamiento")
        tratamiento_id = res_ins.data[0]["id"]

    # 4. Sincronizar medicamentos:
    # Retiramos los medicamentos anteriores del tratamiento y agregamos los vigentes
    _db().table(TABLA_MEDICACION).delete().eq("tratamiento_id", tratamiento_id).execute()

    medicaciones_guardadas = []
    if medicaciones and len(medicaciones) > 0:
        nuevos_meds = []
        for m in medicaciones:
            nombre = m.get("nombre_medicamento")
            if not nombre or not str(nombre).strip():
                continue
            med_dict = {
                "tratamiento_id": tratamiento_id,
                "nombre_medicamento": str(nombre).strip(),
                "dosis": str(m.get("dosis") or "").strip(),
                "frecuencia": str(m.get("frecuencia") or "").strip(),
                "via_administracion": str(m.get("via_administracion") or "Oral").strip(),
                "fecha_inicio": str(m["fecha_inicio"]) if m.get("fecha_inicio") else None,
                "fecha_fin": str(m["fecha_fin"]) if m.get("fecha_fin") else None,
                "activo": m.get("activo", True) is not False,
                "indicaciones_especiales": m.get("indicaciones_especiales") or "",
                "created_at": ahora,
                "updated_at": ahora,
            }
            nuevos_meds.append(med_dict)

        if nuevos_meds:
            res_meds = _db().table(TABLA_MEDICACION).insert(nuevos_meds).execute()
            medicaciones_guardadas = res_meds.data or []

    # 5. Retornar el plan consolidado
    plan_completo = (
        _db().table(TABLA_TRATAMIENTO)
        .select("*")
        .eq("id", tratamiento_id)
        .single()
        .execute()
    )

    resultado = plan_completo.data
    resultado["medicaciones"] = medicaciones_guardadas
    return resultado


def registrar_medicacion_individual(datos: dict) -> dict:
    """
    Registra una medicación individual vinculada a un tratamiento existente.
    Valida estrictamente que la fecha de fin sea posterior a la de inicio.
    """
    tratamiento_id = str(datos.get("tratamiento_id"))
    res_trat = _db().table(TABLA_TRATAMIENTO).select("id").eq("id", tratamiento_id).execute()
    if not res_trat.data:
        raise ValueError("El tratamiento especificado no existe en el sistema.")

    f_ini = datos.get("fecha_inicio")
    f_fin = datos.get("fecha_fin")
    if f_ini and f_fin and str(f_fin) <= str(f_ini):
        raise ValueError("La fecha de fin de la medicación debe ser estrictamente posterior a la fecha de inicio.")

    ahora = datetime.now(timezone.utc).isoformat()
    nuevo_med = {
        "tratamiento_id": tratamiento_id,
        "nombre_medicamento": str(datos["nombre_medicamento"]).strip(),
        "dosis": str(datos["dosis"]).strip(),
        "frecuencia": str(datos["frecuencia"]).strip(),
        "via_administracion": str(datos.get("via_administracion") or "Oral").strip(),
        "fecha_inicio": str(f_ini) if f_ini else None,
        "fecha_fin": str(f_fin) if f_fin else None,
        "activo": datos.get("activo", True) is not False,
        "indicaciones_especiales": datos.get("indicaciones_especiales") or "",
        "created_at": ahora,
        "updated_at": ahora,
    }

    res = _db().table(TABLA_MEDICACION).insert(nuevo_med).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    raise Exception("No se pudo registrar la medicación en el sistema.")
