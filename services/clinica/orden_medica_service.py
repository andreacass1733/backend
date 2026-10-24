"""
Servicio para la emisión y gestión de Órdenes Médicas de Laboratorio y Ecografía.
Permite prescribir análisis hormonales, metabólicos y estudios ecográficos según Criterios de Rotterdam.
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from db.supabase_client import supabase
from schemas.clinica.orden_medica_schema import OrdenMedicaCreate, OrdenMedicaResponse, OrdenMedicaListResponse
from services.auth.auditoria_service import registrar_evento_auditoria
from services.clinica.medico_service import obtener_medico_predeterminado_id

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_SQLITE_PATH = os.path.join(BASE_DIR, "db", "audit_trail.db")


def _get_connection():
    conn = sqlite3.connect(DB_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite_table():
    conn = _get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_medicas (
        id TEXT PRIMARY KEY,
        paciente_id TEXT NOT NULL,
        consulta_id TEXT,
        medico_id TEXT,
        fecha_emision TEXT,
        tipo_ecografia TEXT,
        indicacion_ecografia TEXT,
        examenes_laboratorio TEXT,
        indicaciones_preanaliticas TEXT,
        diagnostico_presuntivo TEXT,
        estado TEXT DEFAULT 'vigente',
        prioridad TEXT DEFAULT 'normal',
        observaciones TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()


def crear_orden_medica(datos: OrdenMedicaCreate, medico_id: Optional[str] = None) -> OrdenMedicaResponse:
    """
    Crea y emite una nueva orden médica de exámenes de laboratorio y ecografía.
    """
    _init_sqlite_table()
    ahora_iso = datetime.now(timezone.utc).isoformat()
    orden_id = str(uuid.uuid4())

    # 1. Recuperar información de la paciente
    paciente_res = supabase.table("paciente").select("*").eq("id", datos.paciente_id).execute()
    if not paciente_res.data or len(paciente_res.data) == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Paciente no encontrada para emitir la orden médica.")
    paciente_obj = paciente_res.data[0]
    
    nombres_pac = [paciente_obj.get("nombre", ""), paciente_obj.get("primer_apellido", ""), paciente_obj.get("segundo_apellido", "")]
    paciente_nombre = " ".join(p.strip() for p in nombres_pac if p and p.strip()) or "Paciente Registrada"
    paciente_ci = str(paciente_obj.get("ci") or "")

    # 2. Recuperar información del médico
    m_id = medico_id or datos.medico_id
    medico_obj = None
    if not m_id:
        m_id = obtener_medico_predeterminado_id()

    if m_id:
        try:
            m_res = supabase.table("medico").select("*").eq("id", m_id).execute()
            if m_res.data and len(m_res.data) > 0:
                medico_obj = m_res.data[0]
        except Exception:
            pass

    if not medico_obj:
        medico_obj = {}

    partes_med = [medico_obj.get("nombre", ""), medico_obj.get("primer_apellido", ""), medico_obj.get("segundo_apellido", "")]
    medico_nombre = "Dr. " + " ".join(p.strip() for p in partes_med if p and p.strip()) if any(partes_med) else "Dr. Rodrigo Espinoza Iturri"
    medico_especialidad = medico_obj.get("especialidad", "Endocrinología y Ginecología")
    medico_matricula = medico_obj.get("matricula_profesional", "MP-49201-LP")
    medico_final_id = medico_obj.get("id") or m_id

    # 3. Guardar en SQLite
    examenes_json = json.dumps(datos.examenes_laboratorio, default=str)
    conn = _get_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO ordenes_medicas (
        id, paciente_id, consulta_id, medico_id, fecha_emision, tipo_ecografia,
        indicacion_ecografia, examenes_laboratorio, indicaciones_preanaliticas,
        diagnostico_presuntivo, estado, prioridad, observaciones, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        orden_id, datos.paciente_id, datos.consulta_id, medico_final_id,
        ahora_iso, datos.tipo_ecografia, datos.indicacion_ecografia, examenes_json,
        datos.indicaciones_preanaliticas, datos.diagnostico_presuntivo, "vigente",
        datos.prioridad, datos.observaciones, ahora_iso, ahora_iso
    ))
    conn.commit()
    conn.close()

    # 4. Intentar guardar en Supabase (si la tabla orden_medica existe en la base de datos)
    try:
        sb_record = {
            "id": orden_id,
            "paciente_id": datos.paciente_id,
            "consulta_id": datos.consulta_id,
            "medico_id": medico_final_id,
            "fecha_emision": ahora_iso,
            "tipo_ecografia": datos.tipo_ecografia,
            "indicacion_ecografia": datos.indicacion_ecografia,
            "examenes_laboratorio": datos.examenes_laboratorio,
            "indicaciones_preanaliticas": datos.indicaciones_preanaliticas,
            "diagnostico_presuntivo": datos.diagnostico_presuntivo,
            "estado": "vigente",
            "prioridad": datos.prioridad,
            "observaciones": datos.observaciones,
            "created_at": ahora_iso
        }
        supabase.table("orden_medica").insert(sb_record).execute()
    except Exception as e_sb:
        # Si la tabla no existe aún en Supabase, la orden queda perfectamente guardada en SQLite
        pass

    # 5. Registrar evento de auditoría oficial
    cant_examenes = len(datos.examenes_laboratorio)
    desc_eco = f"Ecografía {datos.tipo_ecografia}" if datos.tipo_ecografia != "ninguna" else "Sin ecografía"
    detalle_auditoria = (
        f"Orden médica #{orden_id[:8].upper()} emitida para {paciente_nombre} (CI {paciente_ci}). "
        f"Se solicitaron {cant_examenes} análisis de laboratorio y {desc_eco}."
    )
    try:
        registrar_evento_auditoria(
            usuario=medico_nombre,
            rol=medico_especialidad,
            ip="192.168.1.45",
            estacion="Cons. Especialidad SOP",
            modulo="ORDENES_MEDICAS",
            evento="CREATE_MEDICAL_ORDER",
            detalle=detalle_auditoria,
            estado="AUDIT_OK",
            paciente_id=paciente_ci,
            paciente_nombre=paciente_nombre,
            payload_json={
                "orden_id": orden_id,
                "paciente_id": datos.paciente_id,
                "tipo_ecografia": datos.tipo_ecografia,
                "examenes_count": cant_examenes,
                "diagnostico": datos.diagnostico_presuntivo
            }
        )
    except Exception as e_aud:
        print("[WARN] Error registrando auditoría para orden médica:", e_aud)

    return OrdenMedicaResponse(
        id=orden_id,
        paciente_id=datos.paciente_id,
        paciente_nombre=paciente_nombre,
        paciente_ci=paciente_ci,
        consulta_id=datos.consulta_id,
        medico_id=medico_final_id,
        medico_nombre=medico_nombre,
        medico_especialidad=medico_especialidad,
        medico_matricula=medico_matricula,
        fecha_emision=ahora_iso,
        tipo_ecografia=datos.tipo_ecografia,
        indicacion_ecografia=datos.indicacion_ecografia,
        examenes_laboratorio=datos.examenes_laboratorio,
        indicaciones_preanaliticas=datos.indicaciones_preanaliticas,
        diagnostico_presuntivo=datos.diagnostico_presuntivo,
        estado="vigente",
        prioridad=datos.prioridad,
        observaciones=datos.observaciones,
        created_at=ahora_iso
    )


def obtener_ordenes_por_paciente(paciente_id: str) -> List[OrdenMedicaResponse]:
    """
    Retorna todas las órdenes médicas emitidas para una paciente, ordenadas de la más reciente a la más antigua.
    """
    _init_sqlite_table()
    
    # 1. Intentar primero en Supabase si la tabla existe
    try:
        res_sb = (
            supabase.table("orden_medica")
            .select("*")
            .eq("paciente_id", paciente_id)
            .order("created_at", desc=True)
            .execute()
        )
        if res_sb.data and len(res_sb.data) > 0:
            return [_formatear_orden_response(row) for row in res_sb.data]
    except Exception:
        pass

    # 2. Consultar SQLite
    conn = _get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT * FROM ordenes_medicas
    WHERE paciente_id = ?
    ORDER BY created_at DESC
    """, (paciente_id,))
    rows = c.fetchall()
    conn.close()

    return [_formatear_orden_response(dict(r)) for r in rows]


def obtener_orden_por_id(orden_id: str) -> Optional[OrdenMedicaResponse]:
    """
    Obtiene los datos completos de una orden médica específica por su UUID.
    """
    _init_sqlite_table()

    # 1. Supabase
    try:
        res_sb = supabase.table("orden_medica").select("*").eq("id", orden_id).execute()
        if res_sb.data and len(res_sb.data) > 0:
            return _formatear_orden_response(res_sb.data[0])
    except Exception:
        pass

    # 2. SQLite
    conn = _get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM ordenes_medicas WHERE id = ?", (orden_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return _formatear_orden_response(dict(row))


def cancelar_orden_medica(orden_id: str) -> bool:
    """
    Cambia el estado de la orden a 'cancelada'.
    """
    _init_sqlite_table()
    ahora_iso = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    c = conn.cursor()
    c.execute("UPDATE ordenes_medicas SET estado = 'cancelada', updated_at = ? WHERE id = ?", (ahora_iso, orden_id))
    conn.commit()
    conn.close()

    try:
        supabase.table("orden_medica").update({"estado": "cancelada", "updated_at": ahora_iso}).eq("id", orden_id).execute()
    except Exception:
        pass

    return True


def _formatear_orden_response(raw: Dict[str, Any]) -> OrdenMedicaResponse:
    # Resolver paciente
    pac_id = raw.get("paciente_id")
    paciente_nombre = "Paciente Registrada"
    paciente_ci = ""
    if pac_id:
        try:
            p_res = supabase.table("paciente").select("nombre, primer_apellido, segundo_apellido, ci").eq("id", pac_id).execute()
            if p_res.data and len(p_res.data) > 0:
                p_obj = p_res.data[0]
                nombres = [p_obj.get("nombre", ""), p_obj.get("primer_apellido", ""), p_obj.get("segundo_apellido", "")]
                paciente_nombre = " ".join(n.strip() for n in nombres if n and n.strip())
                paciente_ci = str(p_obj.get("ci") or "")
        except Exception:
            pass

    # Parsear lista de exámenes si viene como string
    examenes = raw.get("examenes_laboratorio") or []
    if isinstance(examenes, str):
        try:
            examenes = json.loads(examenes)
        except Exception:
            examenes = []

    return OrdenMedicaResponse(
        id=raw["id"],
        paciente_id=raw["paciente_id"],
        paciente_nombre=paciente_nombre,
        paciente_ci=paciente_ci,
        consulta_id=raw.get("consulta_id"),
        medico_id=raw.get("medico_id"),
        medico_nombre="Dr. Rodrigo Espinoza Iturri",
        medico_especialidad="Endocrinología y Ginecología",
        medico_matricula="MP-49201-LP",
        fecha_emision=raw.get("fecha_emision") or raw.get("created_at") or "",
        tipo_ecografia=raw.get("tipo_ecografia") or "transvaginal",
        indicacion_ecografia=raw.get("indicacion_ecografia"),
        examenes_laboratorio=examenes,
        indicaciones_preanaliticas=raw.get("indicaciones_preanaliticas"),
        diagnostico_presuntivo=raw.get("diagnostico_presuntivo"),
        estado=raw.get("estado") or "vigente",
        prioridad=raw.get("prioridad") or "normal",
        observaciones=raw.get("observaciones"),
        created_at=raw.get("created_at")
    )
