from typing import List, Optional
from datetime import datetime, timezone
from db.supabase_client import supabase
from schemas.clinica.consulta_schema import ConsultaCreate, ConsultaUpdate
from services.clinica import medico_service

def _formatear_fecha_atencion(fecha_str: Optional[str]) -> str:
    if not fecha_str:
        return datetime.now(timezone.utc).isoformat()
    if "T" in str(fecha_str):
        return str(fecha_str)
    return f"{fecha_str}T09:00:00Z"

def crear_consulta(consulta: ConsultaCreate) -> dict:
    datos = consulta.model_dump(exclude_unset=True)
    fecha_prox = datos.pop("fecha_proxima_cita", None)
    
    if not datos.get("medico_id"):
        datos["medico_id"] = medico_service.obtener_medico_predeterminado_id()
        
    cita_id = datos.get("cita_id")
    
    # Si viene cita_id, verificar si realmente existe en la tabla cita de forma segura
    if cita_id:
        try:
            res_cita = supabase.table("cita").select("*").eq("id", cita_id).execute()
            if not res_cita.data or len(res_cita.data) == 0:
                datos["cita_id"] = None
            else:
                # Si existe la cita, verificar si ya tiene consulta vinculada para evitar duplicados
                res_exist = supabase.table("consulta").select("*").eq("cita_id", cita_id).execute()
                if res_exist.data and len(res_exist.data) > 0:
                    if fecha_prox:
                        supabase.table("cita").insert({
                            "paciente_id": res_exist.data[0].get("paciente_id"),
                            "medico_id": res_exist.data[0].get("medico_id"),
                            "fecha_atencion": _formatear_fecha_atencion(fecha_prox),
                            "fecha_proxima_cita": str(fecha_prox).split("T")[0],
                            "motivo": "Próximo control de seguimiento SOP",
                            "observaciones": "Programado desde consulta médica",
                            "estado": "programada"
                        }).execute()
                    return res_exist.data[0]
        except Exception as e_cita:
            print("Cita ID invalido o no encontrado, se creara una nueva cita:", e_cita)
            datos["cita_id"] = None

    # Si no tiene cita_id o la cita previa no existía, crear la cita de atención actual con estado 'atendida'
    if not datos.get("cita_id"):
        paciente_id = datos.get("paciente_id")
        if not paciente_id:
            raise Exception("Debe seleccionar una paciente para registrar la consulta médica")
        
        # Buscar si ya existe una cita agendada o atendida hoy para evitar duplicados
        try:
            from datetime import datetime, timezone, timedelta
            limite_reciente = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
            res_cita_existente = (
                supabase.table("cita")
                .select("id")
                .eq("paciente_id", paciente_id)
                .gte("created_at", limite_reciente)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if res_cita_existente.data and len(res_cita_existente.data) > 0:
                datos["cita_id"] = res_cita_existente.data[0]["id"]
        except Exception as e_chk_cita:
            print("[WARN] Error buscando cita existente de hoy:", e_chk_cita)

        if not datos.get("cita_id"):
            cita_datos = {
                "paciente_id": paciente_id,
                "medico_id": datos.get("medico_id"),
                "motivo": datos.get("motivo") or "Consulta médica directa",
                "observaciones": datos.get("observaciones"),
                "estado": "atendida"
            }
            res_cita_nueva = supabase.table("cita").insert(cita_datos).execute()
            if res_cita_nueva.data:
                datos["cita_id"] = res_cita_nueva.data[0]["id"]
            else:
                raise Exception("No se pudo generar el registro de cita requerido para la consulta")

    res = supabase.table("consulta").insert(datos).execute()
    if res.data:
        # Asegurar que la cita de esta consulta quede marcada como atendida
        if datos.get("cita_id"):
            supabase.table("cita").update({"estado": "atendida"}).eq("id", datos["cita_id"]).execute()

        # Generar la próxima cita futura de control en estado 'programada'
        if fecha_prox:
            try:
                supabase.table("cita").insert({
                    "paciente_id": datos.get("paciente_id"),
                    "medico_id": datos.get("medico_id"),
                    "fecha_atencion": _formatear_fecha_atencion(fecha_prox),
                    "fecha_proxima_cita": str(fecha_prox).split("T")[0],
                    "motivo": "Próximo control de seguimiento SOP",
                    "observaciones": "Programado desde consulta médica",
                    "estado": "programada"
                }).execute()
            except Exception as e_prox:
                print("Error al agendar fecha_proxima_cita automática:", e_prox)

        return res.data[0]
    raise Exception("No se pudo crear la consulta médica")

def obtener_consultas(paciente_id: Optional[str] = None, medico_id: Optional[str] = None) -> List[dict]:
    query = supabase.table("consulta").select("*")
    if paciente_id:
        query = query.eq("paciente_id", paciente_id)
    if medico_id:
        query = query.eq("medico_id", medico_id)
    res = query.order("created_at", desc=True).execute()
    return res.data or []

def obtener_consulta_por_id(consulta_id: str) -> Optional[dict]:
    res = supabase.table("consulta").select("*").eq("id", consulta_id).execute()
    if res.data:
        return res.data[0]
    return None

def actualizar_consulta(consulta_id: str, consulta: ConsultaUpdate) -> Optional[dict]:
    datos = consulta.model_dump(exclude_none=True)
    datos["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = supabase.table("consulta").update(datos).eq("id", consulta_id).execute()
    if res.data and len(res.data) > 0:
        consulta_actualizada = res.data[0]
        cita_id = consulta_actualizada.get("cita_id")
        nuevo_estado = datos.get("estado")
        if cita_id and nuevo_estado:
            if nuevo_estado in ["completada", "finalizada"]:
                supabase.table("cita").update({"estado": "atendida"}).eq("id", cita_id).execute()
            elif nuevo_estado == "cancelada":
                supabase.table("cita").update({"estado": "cancelada"}).eq("id", cita_id).execute()
        return consulta_actualizada
    return None

def eliminar_consulta(consulta_id: str) -> bool:
    res = supabase.table("consulta").delete().eq("id", consulta_id).execute()
    return bool(res.data)

def obtener_comparativa_paciente(paciente_id: str) -> dict:
    """
    HU-019: Genera la comparativa cronológica y de evolución clínica/hormonal/ecográfica
    entre las diferentes consultas de una paciente para evaluar progresión o respuesta terapéutica.
    """
    import uuid
    try:
        uuid.UUID(str(paciente_id))
    except Exception:
        return {
            "habilitada": False,
            "total_consultas": 0,
            "mensaje": "Identificador de paciente no válido o sin formato UUID.",
            "consultas": [],
            "deltas": {},
            "resumen_clinico": "Sin datos previos para comparar."
        }

    from db.supabase_client import get_supabase_admin_client
    db = get_supabase_admin_client()

    res_cons = (
        db.table("consulta")
        .select("*")
        .eq("paciente_id", paciente_id)
        .order("created_at", desc=False)
        .execute()
    )
    consultas = res_cons.data or []

    if not consultas:
        return {
            "habilitada": False,
            "total_consultas": 0,
            "mensaje": "La paciente no cuenta con consultas médicas registradas en el sistema.",
            "consultas": [],
            "deltas": {},
            "resumen_clinico": "Sin datos previos para comparar."
        }

    consulta_ids = [c["id"] for c in consultas]

    # Obtener datos clínicos asociados
    dc_map = {}
    try:
        res_dc = db.table("datos_clinicos").select("*").in_("consulta_id", consulta_ids).execute()
        for dc in (res_dc.data or []):
            dc_map[dc["consulta_id"]] = dc
    except Exception as e:
        print("[WARN] Error cargando datos_clinicos para comparativa:", e)

    # Obtener datos hormonales asociados
    dh_map = {}
    try:
        res_dh = db.table("datos_hormonales").select("*").in_("consulta_id", consulta_ids).execute()
        for dh in (res_dh.data or []):
            dh_map[dh["consulta_id"]] = dh
    except Exception as e:
        print("[WARN] Error cargando datos_hormonales para comparativa:", e)

    # Obtener estudios ecográficos asociados
    ee_map = {}
    try:
        res_ee = db.table("estudio_ecografico").select("*").in_("consulta_id", consulta_ids).execute()
        for ee in (res_ee.data or []):
            ee_map[ee["consulta_id"]] = ee
    except Exception as e:
        print("[WARN] Error cargando estudio_ecografico para comparativa:", e)

    timeline = []
    for c in consultas:
        cid = c["id"]
        dc = dc_map.get(cid) or {}
        dh = dh_map.get(cid) or {}
        ee = ee_map.get(cid) or {}

        c1 = bool(dc.get("amenorrea") or dc.get("oligomenorrea") or dc.get("ciclos_irregulares") or (dc.get("duracion_ciclo_dias") and float(dc.get("duracion_ciclo_dias") or 0) > 35))
        c2 = bool(dc.get("hirsutismo") or (dc.get("score_ferriman_gallwey") and int(dc.get("score_ferriman_gallwey") or 0) >= 8) or (dh.get("testosterona_total") and float(dh.get("testosterona_total") or 0) > 50.0))
        c3 = bool(ee.get("resultado") == "SOP" or (ee.get("prob_sop") and float(ee.get("prob_sop") or 0) >= 0.5) or (ee.get("num_foliculos") and int(ee.get("num_foliculos") or 0) >= 12))

        fenotipo = "Sin Evaluar"
        if dc or dh or ee:
            if c1 and c2 and c3:
                fenotipo = "Fenotipo A"
            elif c1 and c2 and not c3:
                fenotipo = "Fenotipo B"
            elif not c1 and c2 and c3:
                fenotipo = "Fenotipo C"
            elif c1 and not c2 and c3:
                fenotipo = "Fenotipo D"
            else:
                fenotipo = "Sin Criterio SOP" if sum([c1, c2, c3]) < 2 else "En Evaluación"

        punto = {
            "consulta_id": cid,
            "fecha": c["created_at"],
            "motivo": c.get("motivo") or "Consulta Médica",
            "estado": c.get("estado") or "atendida",
            "observaciones": c.get("observaciones"),
            "peso_kg": dc.get("peso_kg"),
            "talla_cm": dc.get("talla_cm"),
            "imc": dc.get("imc"),
            "circunferencia_abdominal_cm": dc.get("circunferencia_abdominal_cm"),
            "duracion_ciclo_dias": dc.get("duracion_ciclo_dias"),
            "score_ferriman_gallwey": dc.get("score_ferriman_gallwey"),
            "acne_gags_grado": dc.get("acne_gags_grado"),
            "alopecia_ludwig_grado": dc.get("alopecia_ludwig_grado"),
            "lh": dh.get("lh"),
            "fsh": dh.get("fsh"),
            "relacion_lh_fsh": dh.get("relacion_lh_fsh"),
            "testosterona_total": dh.get("testosterona_total"),
            "dhea_s": dh.get("dhea_s"),
            "insulina_basal": dh.get("insulina_basal"),
            "glucosa_basal": dh.get("glucosa_basal"),
            "homa_ir": dh.get("homa_ir"),
            "progesterona": dh.get("progesterona"),
            "amh": dh.get("amh"),
            "num_foliculos": ee.get("num_foliculos"),
            "resultado_eco": ee.get("resultado") or ("SOP" if ee.get("prob_sop", 0) >= 0.5 else ("Normal" if ee.get("prob_sop") is not None else None)),
            "prob_sop": ee.get("prob_sop"),
            "imagen_url": ee.get("imagen_url"),
            "fenotipo_rotterdam": fenotipo,
            "criterios": {
                "criterio1": c1,
                "criterio2": c2,
                "criterio3": c3
            }
        }
        timeline.append(punto)

    total_evaluaciones = len(timeline)
    habilitada = total_evaluaciones >= 2

    deltas = {}
    resumen_clinico = ""

    if habilitada:
        consultas_con_datos = [p for p in timeline if p.get("imc") is not None or p.get("lh") is not None or p.get("num_foliculos") is not None]
        primera = consultas_con_datos[0] if consultas_con_datos else timeline[0]
        ultima = consultas_con_datos[-1] if consultas_con_datos else timeline[-1]

        def _calc_delta(val_fin, val_ini, unidad="", menor_es_mejor=True):
            if val_fin is None or val_ini is None:
                return None
            try:
                fin = float(val_fin)
                ini = float(val_ini)
                diff = round(fin - ini, 2)
                if diff == 0:
                    tendencia = "estable"
                    color = "text-slate-600 bg-slate-100"
                    signo = "="
                elif (diff < 0 and menor_es_mejor) or (diff > 0 and not menor_es_mejor):
                    tendencia = "mejoria"
                    color = "text-emerald-700 bg-emerald-100"
                    signo = "↓" if diff < 0 else "↑"
                else:
                    tendencia = "alerta"
                    color = "text-rose-700 bg-rose-100"
                    signo = "↑" if diff > 0 else "↓"
                return {
                    "inicial": ini,
                    "actual": fin,
                    "diferencia": diff,
                    "unidad": unidad,
                    "tendencia": tendencia,
                    "color": color,
                    "icono": signo
                }
            except Exception:
                return None

        deltas = {
            "imc": _calc_delta(ultima.get("imc"), primera.get("imc"), "kg/m²", menor_es_mejor=True),
            "lh_fsh": _calc_delta(ultima.get("relacion_lh_fsh"), primera.get("relacion_lh_fsh"), "", menor_es_mejor=True),
            "testosterona": _calc_delta(ultima.get("testosterona_total"), primera.get("testosterona_total"), "ng/dL", menor_es_mejor=True),
            "ferriman": _calc_delta(ultima.get("score_ferriman_gallwey"), primera.get("score_ferriman_gallwey"), "pts", menor_es_mejor=True),
            "homa_ir": _calc_delta(ultima.get("homa_ir"), primera.get("homa_ir"), "", menor_es_mejor=True),
            "foliculos": _calc_delta(ultima.get("num_foliculos"), primera.get("num_foliculos"), "folículos", menor_es_mejor=True),
        }

        mejoras = []
        alertas = []
        if deltas.get("imc") and deltas["imc"]["tendencia"] == "mejoria": mejoras.append(f"reducción de IMC ({abs(deltas['imc']['diferencia'])} kg/m²)")
        if deltas.get("lh_fsh") and deltas["lh_fsh"]["tendencia"] == "mejoria": mejoras.append("balance LH/FSH favorable")
        if deltas.get("testosterona") and deltas["testosterona"]["tendencia"] == "mejoria": mejoras.append(f"reducción de andrógenos ({abs(deltas['testosterona']['diferencia'])} ng/dL)")
        if deltas.get("homa_ir") and deltas["homa_ir"]["tendencia"] == "mejoria": mejoras.append("sensibilización insulínica (menor HOMA-IR)")
        if deltas.get("foliculos") and deltas["foliculos"]["tendencia"] == "mejoria": mejoras.append(f"disminución folicular ({abs(deltas['foliculos']['diferencia'])} folículos)")

        if deltas.get("imc") and deltas["imc"]["tendencia"] == "alerta": alertas.append("aumento de IMC")
        if deltas.get("testosterona") and deltas["testosterona"]["tendencia"] == "alerta": alertas.append("aumento de testosterona")

        resumen_clinico = "Evolución clínica favorable: " + ", ".join(mejoras) + "." if mejoras else "Valores clínicos y metabólicos en control periódico."
        if alertas:
            resumen_clinico += " Se observa: " + ", ".join(alertas) + "; valorar ajuste en esquema terapéutico."
    else:
        resumen_clinico = "Se requieren al menos dos consultas registradas para calcular las variaciones (HU-019)."

    return {
        "habilitada": habilitada,
        "total_consultas": total_evaluaciones,
        "mensaje": "Comparativa evolutiva generada con éxito." if habilitada else "Se requieren al menos dos consultas registradas para generar la comparativa evolutiva (HU-019).",
        "consultas": timeline,
        "deltas": deltas,
        "resumen_clinico": resumen_clinico
    }
