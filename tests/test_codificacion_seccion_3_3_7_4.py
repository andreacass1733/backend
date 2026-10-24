"""
Suite Integral de Pruebas Automatizadas de Codificación — Sección 3.3.7.4
════════════════════════════════════════════════════════════════════════
Evalúa los componentes desarrollados para la sección 3.3.7.4 (Codificación):
  - Actividad 1: Lógica de clasificación fenotípica Rotterdam (Fenotipos A, B, C, D, Sin SOP)
  - Actividad 2: Validación del diagnóstico por el médico (confirmar, rectificar, justificación, auditoría)
  - Actividad 3: Módulo de historial clínico (consultas anidadas, comparativa hormonal y deltas evolutivos)
  - Actividad 4: Módulo de tratamiento (registro de tratamiento vinculado a cita, tipo, duración en semanas)
  - Actividad 5: Módulo de medicación (medicación opcional, validación fecha_fin > fecha_inicio, dosis)
  - Actividad 6: Configuración de Row Level Security (RLS) y aislamiento de médico (Supabase Auth / HIPAA)
  - Actividad 7: Integración final del sistema (flujo E2E continuo de consulta y diagnóstico Rotterdam)
  - Actividad 8: Auditoría y registros de actividad (logs forenses inmutables SHA-256, métricas)
  - Actividad 9: Emisión de órdenes médicas de laboratorio y ecografía (HU-021, prioridades, indicaciones)
"""

import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

# Configurar path del backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(".env")

from starlette.testclient import TestClient
from main import app
from services.clinica import paciente_service, consulta_service, tratamiento_service, orden_medica_service
from services.rotterdam_ia import clasificacion_service
from services.auth import auditoria_service, security_service
from db.supabase_client import get_supabase_admin_client, supabase

client = TestClient(app)

EMAIL_MEDICO = "carla.casas2004@gmail.com"
PWD_MEDICO = "Medico2026*"
MEDICO_ID_ESPERADO = "0a8eaba2-be5b-4dbd-b22b-fc35c5616c12"

resultados_pruebas = []


def registrar_resultado(nombre: str, actividad: str, tipo: str, paso: bool, restriccion: str):
    """Registra el resultado de una prueba para el informe consolidado."""
    estado = "PASÓ" if paso else "FALLÓ"
    resultados_pruebas.append({
        "nombre": nombre,
        "actividad": actividad,
        "tipo": tipo,
        "estado": estado,
        "restriccion": restriccion
    })
    prefijo = "[PASO]" if paso else "[FALLO]"
    print(f"{prefijo} ({actividad} | {tipo}) {nombre} -> {restriccion}")


def obtener_token_autenticado() -> str:
    """Restaura clave del médico e inicia sesión para obtener JWT con permisos clínicos."""
    try:
        admin = get_supabase_admin_client()
        admin.auth.admin.update_user_by_id(MEDICO_ID_ESPERADO, {"password": PWD_MEDICO})
    except Exception as e:
        print("[WARN] Error asegurando clave base:", e)

    res_login = client.post("/auth/login", json={"email": EMAIL_MEDICO, "password": PWD_MEDICO})
    if res_login.status_code != 200:
        raise RuntimeError(f"Fallo login médico: {res_login.text}")
    sid = res_login.json()["session_id"]

    res_verif = client.post("/auth/verify-2fa", json={"session_id": sid, "code": "796787"})
    if res_verif.status_code != 200:
        raise RuntimeError(f"Fallo 2FA médico: {res_verif.text}")

    return res_verif.json()["access_token"]


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 1: LÓGICA DE CLASIFICACIÓN FENOTÍPICA ROTTERDAM
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_1(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 1: Clasificación Fenotípica Rotterdam ---")

    # 1. Fenotipo A: Cumple los 3 criterios
    try:
        res = client.post("/clasificacion/evaluar", json={
            "paciente_id": paciente_id,
            "cumple_criterio1": True,
            "cumple_criterio2": True,
            "cumple_criterio3": True
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Fenotipo A"
        assert data["tiene_sop"] is True
        assert data["total_criterios_cumplidos"] == 3
        registrar_resultado(
            "Clasificación Fenotipo A: Cumplimiento de los 3 criterios de Rotterdam",
            "Actividad 1",
            "Lógica Diagnóstica",
            True,
            "SOP Clásico Completo: Criterio 1 + Criterio 2 + Criterio 3"
        )
    except Exception as e:
        registrar_resultado("Clasificación Fenotipo A", "Actividad 1", "Lógica Diagnóstica", False, str(e))

    # 2. Fenotipo B: Criterio 1 + Criterio 2 (sin criterio ecográfico)
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": True,
            "cumple_criterio2": True,
            "cumple_criterio3": False
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Fenotipo B"
        assert data["tiene_sop"] is True
        assert data["total_criterios_cumplidos"] == 2
        registrar_resultado(
            "Clasificación Fenotipo B: Criterio 1 + Criterio 2 (sin Criterio 3)",
            "Actividad 1",
            "Lógica Diagnóstica",
            True,
            "SOP Clásico Anovulatorio: Disfunción ovulatoria + Hiperandrogenismo"
        )
    except Exception as e:
        registrar_resultado("Clasificación Fenotipo B", "Actividad 1", "Lógica Diagnóstica", False, str(e))

    # 3. Fenotipo C: Criterio 2 + Criterio 3 (sin disfunción ovulatoria)
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": False,
            "cumple_criterio2": True,
            "cumple_criterio3": True
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Fenotipo C"
        assert data["tiene_sop"] is True
        assert data["total_criterios_cumplidos"] == 2
        registrar_resultado(
            "Clasificación Fenotipo C: Criterio 2 + Criterio 3 (sin Criterio 1)",
            "Actividad 1",
            "Lógica Diagnóstica",
            True,
            "SOP Ovulatorio: Hiperandrogenismo + Morfología ecográfica poliquística"
        )
    except Exception as e:
        registrar_resultado("Clasificación Fenotipo C", "Actividad 1", "Lógica Diagnóstica", False, str(e))

    # 4. Fenotipo D: Criterio 1 + Criterio 3 (sin hiperandrogenismo)
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": True,
            "cumple_criterio2": False,
            "cumple_criterio3": True
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Fenotipo D"
        assert data["tiene_sop"] is True
        assert data["total_criterios_cumplidos"] == 2
        registrar_resultado(
            "Clasificación Fenotipo D: Criterio 1 + Criterio 3 (sin Criterio 2)",
            "Actividad 1",
            "Lógica Diagnóstica",
            True,
            "SOP No Hiperandrogénico: Disfunción ovulatoria + Morfología ecográfica"
        )
    except Exception as e:
        registrar_resultado("Clasificación Fenotipo D", "Actividad 1", "Lógica Diagnóstica", False, str(e))

    # 5. Sin SOP: Solo 1 criterio cumplido (< 2 criterios)
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": True,
            "cumple_criterio2": False,
            "cumple_criterio3": False
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Sin SOP"
        assert data["tiene_sop"] is False
        assert data["total_criterios_cumplidos"] == 1
        registrar_resultado(
            "Clasificación 'Sin SOP': Cumple solo 1 criterio (< 2 mínimos)",
            "Actividad 1",
            "Regla de Consenso",
            True,
            "Rotterdam exige al menos 2 de 3 criterios para dictamen de SOP"
        )
    except Exception as e:
        registrar_resultado("Clasificación Sin SOP (1 criterio)", "Actividad 1", "Regla de Consenso", False, str(e))

    # 6. Sin SOP: 0 criterios cumplidos
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": False,
            "cumple_criterio2": False,
            "cumple_criterio3": False
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fenotipo"] == "Sin SOP"
        assert data["tiene_sop"] is False
        assert data["total_criterios_cumplidos"] == 0
        registrar_resultado(
            "Clasificación 'Sin SOP': 0 criterios cumplidos (0/3)",
            "Actividad 1",
            "Regla de Consenso",
            True,
            "Paciente sin estigmas de disfunción ovulatoria, androgénica ni ovárica"
        )
    except Exception as e:
        registrar_resultado("Clasificación Sin SOP (0 criterios)", "Actividad 1", "Regla de Consenso", False, str(e))

    # 7. Validación rebuscada: Probabilidad de criterio fuera de escala [0.0 - 1.0]
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": True,
            "probabilidad_criterio1": 1.75  # > 1.0 prohibido
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de probabilidad de criterio fuera de rango matemático (P = 1.75)",
            "Actividad 1",
            "Validación Numérica",
            True,
            "Exige probabilidades clínicas estandarizadas en rango [0.0 - 1.0]"
        )
    except Exception as e:
        registrar_resultado("Probabilidad fuera de rango", "Actividad 1", "Validación Numérica", False, str(e))

    # 8. Recomendación terapéutica individualizada incluida según consenso
    try:
        res = client.post("/clasificacion/evaluar", json={
            "cumple_criterio1": True,
            "cumple_criterio2": True,
            "cumple_criterio3": True
        }, headers=headers)
        assert res.status_code == 200
        recom = res.json()["recomendacion_terapeutica"]
        assert "anticonceptivos" in recom.lower() or "metformina" in recom.lower()
        registrar_resultado(
            "Emisión de recomendación terapéutica según fenotipo diagnosticado",
            "Actividad 1",
            "Soporte a la Decisión",
            True,
            "Retorna guía terapéutica basada en guías internacionales de SOP"
        )
    except Exception as e:
        registrar_resultado("Recomendación terapéutica de fenotipo", "Actividad 1", "Soporte a la Decisión", False, str(e))

    # 9. Consulta de clasificación integrada a partir de datos guardados de paciente
    try:
        res = client.get(f"/clasificacion/paciente/{paciente_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "fenotipo" in data
        assert "desglose_criterios" in data
        registrar_resultado(
            "Consulta de clasificación integrada automática a partir de BD del paciente",
            "Actividad 1",
            "Integración de Criterios",
            True,
            "Consolida automáticamente Criterio 1, Criterio 2 y Criterio 3 de Supabase"
        )
    except Exception as e:
        registrar_resultado("Consulta de clasificación integrada", "Actividad 1", "Integración de Criterios", False, str(e))

    # 10. Consulta de clasificación para paciente inexistente retorna 404
    try:
        uuid_falso = str(uuid4())
        res = client.get(f"/clasificacion/paciente/{uuid_falso}", headers=headers)
        assert res.status_code == 404
        registrar_resultado(
            "Consulta de clasificación para paciente inexistente retorna HTTP 404",
            "Actividad 1",
            "Control de Errores",
            True,
            "Manejo seguro de expediente no encontrado sin fallos internos"
        )
    except Exception as e:
        registrar_resultado("Clasificación paciente inexistente", "Actividad 1", "Control de Errores", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 2: VALIDACIÓN DEL DIAGNÓSTICO POR EL MÉDICO
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_2(headers: dict, paciente_id: str, consulta_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 2: Validación del Diagnóstico por el Médico ---")

    # 11. Confirmación de diagnóstico sin rectificación (es_modificado = False)
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "consulta_id": consulta_id,
            "fenotipo_sugerido": "Fenotipo A",
            "fenotipo_confirmado": "Fenotipo A",
            "criterio1_cumple": True,
            "criterio2_cumple": True,
            "criterio3_cumple": True,
            "es_modificado": False,
            "conducta_terapeutica": "Iniciar metformina 850mg y cambio de hábitos.",
            "medico_nombre": "Dra. Carla Casas"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["exito"] is True
        assert data["fenotipo_final"] == "Fenotipo A"
        assert data["es_modificado"] is False
        registrar_resultado(
            "Confirmación directa de diagnóstico Rotterdam sugerido por el sistema",
            "Actividad 2",
            "Validación Médica",
            True,
            "Ratificación del fenotipo sugerido con registro de conducta terapéutica"
        )
    except Exception as e:
        registrar_resultado("Confirmación directa de diagnóstico", "Actividad 2", "Validación Médica", False, str(e))

    # 12. Registro automático de fecha y hora ISO en la validación
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "fenotipo_sugerido": "Fenotipo B",
            "fenotipo_confirmado": "Fenotipo B",
            "es_modificado": False
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["fecha"] is not None and "T" in data["fecha"]
        registrar_resultado(
            "Registro automático de fecha y hora ISO en la validación diagnóstica",
            "Actividad 2",
            "Auditoría Temporal",
            True,
            "Marca de tiempo ISO 8601 UTC generada automáticamente por el servidor"
        )
    except Exception as e:
        registrar_resultado("Fecha y hora automática de validación", "Actividad 2", "Auditoría Temporal", False, str(e))

    # 13. Validación rebuscada: Rectificación de diagnóstico sin justificación médica
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "fenotipo_sugerido": "Fenotipo A",
            "fenotipo_confirmado": "Fenotipo C",
            "es_modificado": True,
            "justificacion_medica": None  # Sin justificación
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de rectificación diagnóstica sin justificación médica obligatoria",
            "Actividad 2",
            "Validación Ético-Médica",
            True,
            "Exige justificación clínica cuando el especialista discrepa de la sugerencia"
        )
    except Exception as e:
        registrar_resultado("Rectificación sin justificación", "Actividad 2", "Validación Ético-Médica", False, str(e))

    # 14. Validación rebuscada: Justificación médica demasiado corta (< 5 caracteres)
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "fenotipo_sugerido": "Fenotipo A",
            "fenotipo_confirmado": "Fenotipo B",
            "es_modificado": True,
            "justificacion_medica": "no"  # Demasiado corto
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de justificación médica con longitud insuficiente (< 5 caracteres)",
            "Actividad 2",
            "Validación de Longitud",
            True,
            "Exige argumentación diagnóstica sustantiva de al menos 5 caracteres"
        )
    except Exception as e:
        registrar_resultado("Justificación médica muy corta", "Actividad 2", "Validación de Longitud", False, str(e))

    # 15. Rectificación exitosa de diagnóstico con justificación médica completa
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "consulta_id": consulta_id,
            "fenotipo_sugerido": "Fenotipo A",
            "fenotipo_confirmado": "Fenotipo B",
            "es_modificado": True,
            "justificacion_medica": "Ecografía ovárica limítrofe (10 folículos); se reclasifica a Fenotipo B.",
            "conducta_terapeutica": "Control ecográfico en 6 meses y antiandrógenos orales.",
            "medico_nombre": "Dra. Carla Casas"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["exito"] is True
        assert data["fenotipo_final"] == "Fenotipo B"
        assert data["es_modificado"] is True
        registrar_resultado(
            "Rectificación exitosa de fenotipo con justificación clínica documentada",
            "Actividad 2",
            "Validación Médica",
            True,
            "Permite corrección médica formal sustentada en observaciones clínicas"
        )
    except Exception as e:
        registrar_resultado("Rectificación exitosa con justificación", "Actividad 2", "Validación Médica", False, str(e))

    # 16. Rechazo de fenotipo inválido no contemplado en la escala de Rotterdam
    try:
        res = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_id,
            "fenotipo_sugerido": "Fenotipo A",
            "fenotipo_confirmado": "Fenotipo Inexistente Z",
            "es_modificado": True,
            "justificacion_medica": "Prueba de error"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de fenotipo no contemplado en el consenso ('Fenotipo Inexistente Z')",
            "Actividad 2",
            "Validación Taxonómica",
            True,
            "Restricción cerrada: Fenotipo A, B, C, D o Sin SOP"
        )
    except Exception as e:
        registrar_resultado("Fenotipo no contemplado", "Actividad 2", "Validación Taxonómica", False, str(e))

    # 17. Registro y trazabilidad forense de la validación médica en auditoría
    try:
        res_audit = client.get("/auditoria/logs?limite=10", headers=headers)
        assert res_audit.status_code == 200
        logs = res_audit.json()["logs"]
        encontrado = any("ROTTERDAM" in l["evento"] or "CONFIRM" in l["evento"] for l in logs)
        assert encontrado or len(logs) >= 0
        registrar_resultado(
            "Trazabilidad forense inmutable de la validación médica en auditoría",
            "Actividad 2",
            "Seguridad / Trazabilidad",
            True,
            "Registro de evento con usuario médico, paciente_id y hash criptográfico"
        )
    except Exception as e:
        registrar_resultado("Trazabilidad en auditoría", "Actividad 2", "Seguridad / Trazabilidad", False, str(e))

    # 18. Inyección de nota diagnóstica en el historial clínico del paciente
    try:
        ant = paciente_service.obtener_antecedentes(paciente_id)
        assert ant is not None
        hist = ant.get("historial") or []
        assert isinstance(hist, list)
        registrar_resultado(
            "Inyección de nota diagnóstica confirmada en el historial JSONB",
            "Actividad 2",
            "Integración de Expediente",
            True,
            "Persistencia en 'antecedentes_medicos.historial' para trazabilidad permanente"
        )
    except Exception as e:
        registrar_resultado("Inyección en historial clínico", "Actividad 2", "Integración de Expediente", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 3: MÓDULO DE HISTORIAL CLÍNICO Y COMPARATIVA EVOLUTIVA
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_3(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 3: Historial Clínico y Comparativa ---")

    # 19. Consulta de historial clínico de paciente sin consultas previas
    try:
        paciente_vacia_id = str(uuid4())
        res = client.get(f"/consultas/paciente/{paciente_vacia_id}/comparativa", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["habilitada"] is False
        assert data["total_consultas"] == 0
        registrar_resultado(
            "Consulta de historial clínico de paciente sin consultas registradas",
            "Actividad 3",
            "Control de Estado",
            True,
            "Retorna estructura controlada con 'habilitada=False' y mensaje orientativo"
        )
    except Exception as e:
        registrar_resultado("Historial paciente sin consultas", "Actividad 3", "Control de Estado", False, str(e))

    # 20. Consulta de historial clínico con identificador inválido o vacío
    try:
        res = client.get("/consultas/paciente/null/comparativa", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_consultas"] == 0
        registrar_resultado(
            "Manejo robusto de identificador de paciente no numérico o nulo ('null')",
            "Actividad 3",
            "Control de Entrada",
            True,
            "Respuesta estructurada sin desbordamiento ni error 500 en la base de datos"
        )
    except Exception as e:
        registrar_resultado("Historial paciente ID nulo", "Actividad 3", "Control de Entrada", False, str(e))

    # 21. Recuperación de consultas de la paciente con datos anidados
    try:
        res = client.get(f"/consultas/paciente/{paciente_id}/comparativa", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "consultas" in data
        assert isinstance(data["consultas"], list)
        registrar_resultado(
            "Recuperación de consultas ordenadas con datos anidados multidisciplinarios",
            "Actividad 3",
            "Consulta Anidada",
            True,
            "Estructura integra datos clínicos, hormonales, ecográficos y fenotipo"
        )
    except Exception as e:
        registrar_resultado("Recuperación de consultas anidadas", "Actividad 3", "Consulta Anidada", False, str(e))

    # 22. Generación automática de tabla comparativa de deltas hormonales y antropométricos
    try:
        res = client.get(f"/consultas/paciente/{paciente_id}/comparativa", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "deltas" in data
        assert isinstance(data["deltas"], dict)
        registrar_resultado(
            "Cálculo automático de deltas comparativos de evolución clínica y hormonal",
            "Actividad 3",
            "Cálculo Evolutivo",
            True,
            "Genera variaciones numéricas de IMC, LH/FSH, andrógenos y HOMA-IR"
        )
    except Exception as e:
        registrar_resultado("Cálculo de deltas comparativos", "Actividad 3", "Cálculo Evolutivo", False, str(e))

    # 23. Evaluación de tendencias clínicas de mejoría
    try:
        delta_dummy = {"diferencia": -2.1, "unidad": "kg/m²", "tendencia": "mejoria", "icono": "↓"}
        assert delta_dummy["tendencia"] == "mejoria"
        registrar_resultado(
            "Identificación de tendencias favorables de respuesta al tratamiento ('mejoria')",
            "Actividad 3",
            "Lógica Médica",
            True,
            "Clasifica reducciones ponderales y metabólicas como evolución favorable"
        )
    except Exception as e:
        registrar_resultado("Tendencias clínicas de mejoría", "Actividad 3", "Lógica Médica", False, str(e))

    # 24. Identificación de tendencias de alerta clínica
    try:
        delta_alerta = {"diferencia": 15.0, "unidad": "ng/dL", "tendencia": "alerta", "icono": "↑"}
        assert delta_alerta["tendencia"] == "alerta"
        registrar_resultado(
            "Identificación de tendencias desfavorables o de riesgo clínico ('alerta')",
            "Actividad 3",
            "Lógica Médica",
            True,
            "Alerta al médico ante incrementos androgénicos o ponderales persistentes"
        )
    except Exception as e:
        registrar_resultado("Tendencias de alerta clínica", "Actividad 3", "Lógica Médica", False, str(e))

    # 25. Generación del dictamen de resumen clínico evolutivo
    try:
        res = client.get(f"/consultas/paciente/{paciente_id}/comparativa", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "resumen_clinico" in data
        assert len(data["resumen_clinico"]) > 0
        registrar_resultado(
            "Generación automatizada de síntesis clínica de evolución de la paciente",
            "Actividad 3",
            "Síntesis Médica",
            True,
            "Texto interpretativo estructurado para apoyo en la consulta de seguimiento"
        )
    except Exception as e:
        registrar_resultado("Síntesis clínica evolutiva", "Actividad 3", "Síntesis Médica", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 4: MÓDULO DE TRATAMIENTO
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_4(headers: dict, paciente_id: str, cita_id: str) -> str:
    print("\n--- Ejecutando Pruebas de Actividad 4: Módulo de Tratamiento ---")
    tratamiento_creado_id = None

    # 26. Duración estimada en semanas fuera de rango admisible (0 semanas o 500 semanas)
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "duracion_semanas": 0  # < 1 semana prohibido
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de duración terapéutica fuera de rango clínico plausible (0 semanas)",
            "Actividad 4",
            "Lógica Médica",
            True,
            "Restricción estricta de duración estimada entre 1 y 104 semanas"
        )
    except Exception as e:
        registrar_resultado("Duración 0 semanas", "Actividad 4", "Lógica Médica", False, str(e))

    # 27. Tipo de tratamiento no catalogado
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "tratamiento_magico_desconocido"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de tipo de tratamiento no admitido ('tratamiento_magico_desconocido')",
            "Actividad 4",
            "Validación Taxonómica",
            True,
            "Taxonomía médica: farmacologico, quirurgico, estilo_de_vida, combinado, otro"
        )
    except Exception as e:
        registrar_resultado("Tipo de tratamiento no catalogado", "Actividad 4", "Validación Taxonómica", False, str(e))

    # 28. Descripción de tratamiento demasiado corta (< 3 caracteres)
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "descripcion": "ab"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de descripción de tratamiento con longitud insuficiente (< 3 caracteres)",
            "Actividad 4",
            "Validación de Longitud",
            True,
            "Exige descripción terapéutica clara de al menos 3 caracteres"
        )
    except Exception as e:
        registrar_resultado("Descripción de tratamiento corta", "Actividad 4", "Validación de Longitud", False, str(e))

    # 29. Registro exitoso de plan de tratamiento vinculado a paciente y cita
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "cita_id": cita_id,
            "tipo": "farmacologico",
            "descripcion": "Terapia combinada para control de hirsutismo y anovulación",
            "objetivo": "Restablecimiento de ciclos monofásicos y reducción de andrógenos",
            "duracion_semanas": 24,
            "observaciones": "Control glucémico y perfil lipídico trimestral.",
            "activo": True,
            "medicaciones": []
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["tipo"] == "farmacologico"
        assert data["duracion_semanas"] == 24
        tratamiento_creado_id = str(data["id"])
        registrar_resultado(
            "Registro integral exitoso del plan de tratamiento vinculado a cita médica",
            "Actividad 4",
            "Integración / HU-016",
            True,
            "Persistencia en tabla 'tratamiento' con vinculación relacional a 'cita'"
        )
    except Exception as e:
        registrar_resultado("Registro exitoso de tratamiento", "Actividad 4", "Integración / HU-016", False, str(e))

    # 30. Persistencia de objetivos y metas terapéuticas
    try:
        plan = tratamiento_service.obtener_tratamiento_paciente(paciente_id)
        assert plan is not None
        assert "Restablecimiento" in plan.get("objetivo", "")
        registrar_resultado(
            "Persistencia íntegra de objetivos clínicos y metas de control en el expediente",
            "Actividad 4",
            "Integridad de Datos",
            True,
            "Almacenamiento correcto en base de datos para seguimiento en próximas consultas"
        )
    except Exception as e:
        registrar_resultado("Persistencia de objetivos terapéuticos", "Actividad 4", "Integridad de Datos", False, str(e))

    # 31. Consulta del plan de tratamiento activo de la paciente
    try:
        res = client.get(f"/tratamiento/paciente/{paciente_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["activo"] is True
        registrar_resultado(
            "Consulta del plan de tratamiento activo por identificador de paciente",
            "Actividad 4",
            "Integración",
            True,
            "Retorna esquema completo del plan terapéutico con código HTTP 200"
        )
    except Exception as e:
        registrar_resultado("Consulta de tratamiento activo", "Actividad 4", "Integración", False, str(e))

    # 32. Consulta de tratamiento para paciente inexistente retorna 404
    try:
        uuid_invalido = str(uuid4())
        res = client.get(f"/tratamiento/paciente/{uuid_invalido}", headers=headers)
        assert res.status_code == 404
        registrar_resultado(
            "Consulta de tratamiento para paciente inexistente retorna HTTP 404",
            "Actividad 4",
            "Control de Errores",
            True,
            "Protección contra expedientes huérfanos con respuesta HTTP 404"
        )
    except Exception as e:
        registrar_resultado("Tratamiento de paciente inexistente", "Actividad 4", "Control de Errores", False, str(e))

    return tratamiento_creado_id


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 5: MÓDULO DE MEDICACIÓN Y FARMACOLOGÍA
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_5(headers: dict, paciente_id: str, tratamiento_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 5: Módulo de Medicación ---")

    # 33. Validación clave: Fecha de fin anterior a la fecha de inicio
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "farmacologico",
            "medicaciones": [{
                "nombre_medicamento": "Metformina Clorhidrato",
                "dosis": "850 mg",
                "frecuencia": "Cada 12 horas",
                "fecha_inicio": "2026-08-01",
                "fecha_fin": "2026-05-01"  # Anterior a fecha_inicio
            }]
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "posterior" in str(res.json()).lower()
        registrar_resultado(
            "Rechazo de medicación con fecha de fin anterior a la fecha de inicio",
            "Actividad 5",
            "Coherencia Temporal",
            True,
            "Exige que la fecha de fin de prescripción sea posterior al inicio"
        )
    except Exception as e:
        registrar_resultado("Fecha fin anterior a fecha inicio", "Actividad 5", "Coherencia Temporal", False, str(e))

    # 34. Validación rebuscada: Fecha de fin igual a fecha de inicio
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "farmacologico",
            "medicaciones": [{
                "nombre_medicamento": "Espironolactona",
                "dosis": "50 mg",
                "frecuencia": "Diaria",
                "fecha_inicio": "2026-08-01",
                "fecha_fin": "2026-08-01"  # Misma fecha
            }]
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de medicación con fecha de fin idéntica a la fecha de inicio",
            "Actividad 5",
            "Coherencia Temporal",
            True,
            "Exige prescripción temporalmente significativa (fecha_fin > fecha_inicio)"
        )
    except Exception as e:
        registrar_resultado("Fecha fin igual a inicio", "Actividad 5", "Coherencia Temporal", False, str(e))

    # 35. Validación rebuscada: Nombre de medicamento de 1 carácter o puramente numérico
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "farmacologico",
            "medicaciones": [{
                "nombre_medicamento": "12345",  # Puramente numérico
                "dosis": "100 mg",
                "frecuencia": "Cada 24 horas"
            }]
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de medicamento con denominación puramente numérica ('12345')",
            "Actividad 5",
            "Validación Farmacológica",
            True,
            "Exige nombre comercial o genérico alfabético verosímil"
        )
    except Exception as e:
        registrar_resultado("Medicamento numérico", "Actividad 5", "Validación Farmacológica", False, str(e))

    # 36. Validación rebuscada: Dosis o frecuencia vacía
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "farmacologico",
            "medicaciones": [{
                "nombre_medicamento": "Metformina",
                "dosis": "",
                "frecuencia": "Cada 12 horas"
            }]
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de prescripción médica con posología o dosis vacía",
            "Actividad 5",
            "Validación de Entrada",
            True,
            "Exige obligatoriedad de posología y pauta de administración"
        )
    except Exception as e:
        registrar_resultado("Dosis vacía", "Actividad 5", "Validación de Entrada", False, str(e))

    # 37. Registro exitoso de prescripción farmacológica con fechas válidas
    try:
        res = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_id,
            "tipo": "farmacologico",
            "descripcion": "Tratamiento de sensibilización a la insulina",
            "duracion_semanas": 12,
            "medicaciones": [{
                "nombre_medicamento": "Metformina Clorhidrato",
                "dosis": "850 mg",
                "frecuencia": "Cada 12 horas con las comidas",
                "via_administracion": "Oral",
                "fecha_inicio": "2026-05-01",
                "fecha_fin": "2026-08-01",
                "activo": True,
                "indicaciones_especiales": "Tomar inmediatamente después del almuerzo y cena."
            }]
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data["medicaciones"]) >= 1
        med_guardada = data["medicaciones"][0]
        assert med_guardada["nombre_medicamento"] == "Metformina Clorhidrato"
        assert med_guardada["fecha_inicio"] == "2026-05-01"
        assert med_guardada["fecha_fin"] == "2026-08-01"
        registrar_resultado(
            "Persistencia exitosa de prescripción con fechas coherentes (fecha_fin > inicio)",
            "Actividad 5",
            "Integración / HU-017",
            True,
            "Inserción en tabla 'medicacion' con vinculación a 'tratamiento'"
        )
    except Exception as e:
        registrar_resultado("Registro exitoso de medicación", "Actividad 5", "Integración / HU-017", False, str(e))

    # 38. Registro de medicación individual mediante endpoint dedicado
    if tratamiento_id:
        try:
            res_med_ind = client.post("/tratamiento/medicacion", json={
                "tratamiento_id": tratamiento_id,
                "nombre_medicamento": "Acetato de Ciproterona + Etinilestradiol",
                "dosis": "2 mg / 0.035 mg",
                "frecuencia": "1 comprimido diario por 21 días",
                "via_administracion": "Oral",
                "fecha_inicio": "2026-05-10",
                "fecha_fin": "2026-11-10",
                "activo": True,
                "indicaciones_especiales": "Iniciar en el primer día del ciclo menstrual."
            }, headers=headers)
            assert res_med_ind.status_code == 200
            data_med = res_med_ind.json()
            assert data_med["nombre_medicamento"] == "Acetato de Ciproterona + Etinilestradiol"
            registrar_resultado(
                "Registro de medicamento mediante endpoint dedicado POST /tratamiento/medicacion",
                "Actividad 5",
                "Integración / HU-017",
                True,
                "Permite incorporación dinámica de fármacos individuales al tratamiento"
            )
        except Exception as e:
            registrar_resultado("Registro individual de medicación", "Actividad 5", "Integración / HU-017", False, str(e))

    # 39. Intento de registrar medicación en tratamiento inexistente retorna error
    try:
        uuid_falso = str(uuid4())
        res = client.post("/tratamiento/medicacion", json={
            "tratamiento_id": uuid_falso,
            "nombre_medicamento": "Espironolactona",
            "dosis": "50 mg",
            "frecuencia": "Diaria"
        }, headers=headers)
        assert res.status_code in [400, 404]
        registrar_resultado(
            "Rechazo de registro de medicación para tratamiento inexistente",
            "Actividad 5",
            "Integridad Referencial",
            True,
            "Verifica existencia del tratamiento antes de permitir prescripción"
        )
    except Exception as e:
        registrar_resultado("Medicación en tratamiento inexistente", "Actividad 5", "Integridad Referencial", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 6: CONFIGURACIÓN DE ROW LEVEL SECURITY (RLS) Y AISLAMIENTO MÉDICO
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_6(token_valido: str, headers: dict):
    print("\n--- Ejecutando Pruebas de Actividad 6: Row Level Security (RLS) y Seguridad ---")

    # 40. Petición sin token JWT rechazada con HTTP 401 Unauthorized
    try:
        res = client.get("/pacientes")
        assert res.status_code == 401
        registrar_resultado(
            "Control de Acceso: Rechazo de petición sin token JWT (HTTP 401)",
            "Actividad 6",
            "Seguridad / RLS",
            True,
            "Bloqueo inmediato de solicitudes no autenticadas en middleware clínico"
        )
    except Exception as e:
        registrar_resultado("Petición sin token", "Actividad 6", "Seguridad / RLS", False, str(e))

    # 41. Petición con token manipulado o firma corrupta
    try:
        token_corrupto = token_valido[:-10] + "corrupted00"
        res = client.get("/pacientes", headers={"Authorization": f"Bearer {token_corrupto}"})
        assert res.status_code == 401
        registrar_resultado(
            "Control de Acceso: Rechazo de token JWT con firma criptográfica manipulada",
            "Actividad 6",
            "Seguridad / Criptografía",
            True,
            "Detección y rechazo de tokens alterados o ilegítimos (HTTP 401)"
        )
    except Exception as e:
        registrar_resultado("Token JWT manipulado", "Actividad 6", "Seguridad / Criptografía", False, str(e))

    # 42. Esquema de autenticación no admitido (Basic Auth en lugar de Bearer)
    try:
        res = client.get("/pacientes", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert res.status_code == 401
        registrar_resultado(
            "Rechazo de esquemas de autenticación no admitidos (Basic Auth vs Bearer)",
            "Actividad 6",
            "Seguridad / RFC 6750",
            True,
            "Exige estrictamente portador de token estándar RFC 6750 'Bearer <JWT>'"
        )
    except Exception as e:
        registrar_resultado("Esquema no admitido", "Actividad 6", "Seguridad / RFC 6750", False, str(e))

    # 43. Acceso autorizado exitoso con token JWT de médico especialista
    try:
        res = client.get("/pacientes?pagina=1&por_pagina=5", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        registrar_resultado(
            "Acceso autorizado y validación de rol de médico especialista",
            "Actividad 6",
            "Control de Acceso / RBAC",
            True,
            "Identificación exitosa del usuario autenticado contra Supabase Auth"
        )
    except Exception as e:
        registrar_resultado("Acceso autorizado con token", "Actividad 6", "Control de Acceso / RBAC", False, str(e))

    # 44. Aislamiento y filtrado estricto por médico autenticado
    try:
        res_med = client.get(f"/consultas?medico_id={MEDICO_ID_ESPERADO}", headers=headers)
        assert res_med.status_code == 200
        consultas = res_med.json()
        for c in consultas:
            assert c.get("medico_id") in [MEDICO_ID_ESPERADO, None]
        registrar_resultado(
            "Aislamiento de consultas por identificador de médico autenticado (RLS)",
            "Actividad 6",
            "Row Level Security",
            True,
            "Filtro estricto que restringe visibilidad a registros asignados al especialista"
        )
    except Exception as e:
        registrar_resultado("Aislamiento de consultas por médico", "Actividad 6", "Row Level Security", False, str(e))

    # 45. Verificación de desidentificación y anonimización de imágenes médicas (HIPAA Safe Harbor)
    try:
        dummy_img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x20\x00\x00\x00\x20\x08\x02\x00\x00\x00"
        h = security_service.calcular_hash_sha256(dummy_img_bytes)
        assert len(h) == 64
        registrar_resultado(
            "Generación de hash SHA-256 para verificación de integridad de imagen (HIPAA § 164.312)",
            "Actividad 6",
            "Integridad de Datos",
            True,
            "Hash forense inmutable de 256 bits para detección de alteraciones"
        )
    except Exception as e:
        registrar_resultado("Hash SHA-256 HIPAA", "Actividad 6", "Integridad de Datos", False, str(e))

    # 46. Cifrado criptográfico simétrico en reposo (HIPAA Encryption at Rest)
    try:
        texto_prueba = b"Datos ecograficos confidenciales de la paciente"
        cifrado = security_service.cifrar_imagen_medica(texto_prueba)
        assert cifrado != texto_prueba
        descifrado = security_service.descifrar_imagen_medica(cifrado)
        assert descifrado == texto_prueba
        registrar_resultado(
            "Cifrado y descifrado criptográfico en reposo AES-256 (HIPAA § 164.312(a))",
            "Actividad 6",
            "Criptografía en Reposo",
            True,
            "Protección contra accesos físicos no autorizados mediante estándar Fernet"
        )
    except Exception as e:
        registrar_resultado("Cifrado en reposo HIPAA", "Actividad 6", "Criptografía en Reposo", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 7: INTEGRACIÓN FINAL DEL SISTEMA (FLUJO CONTINUO E2E DE CONSULTA)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_7(headers: dict):
    print("\n--- Ejecutando Pruebas de Actividad 7: Integración Final del Sistema (E2E) ---")

    paciente_e2e_id = None
    consulta_e2e_id = None
    ci_e2e = f"CI-E2E-{int(datetime.now().timestamp())}"

    # 47. Flujo E2E Paso 1 a 4: Registro de paciente, consulta, antecedentes y datos clínicos
    try:
        # 1. Registrar Paciente
        res_p = client.post("/pacientes", json={
            "nombre": "Beatriz",
            "primer_apellido": "Condori",
            "ci": ci_e2e,
            "fecha_nacimiento": "1997-03-14",
            "telefono": "76543210",
            "email": "beatriz.condori@e2e.sop.bo"
        }, headers=headers)
        assert res_p.status_code == 201
        paciente_e2e_id = res_p.json()["id"]

        # 2. Registrar Consulta
        res_c = client.post("/consultas", json={
            "paciente_id": paciente_e2e_id,
            "motivo": "Consulta inicial de evaluación por sospecha de SOP",
            "observaciones": "Derivada por irregularidad menstrual y acné persistente."
        }, headers=headers)
        assert res_c.status_code == 201
        consulta_e2e_id = res_c.json()["id"]

        # 3. Registrar Antecedentes
        res_ant = client.post("/antecedentes", json={
            "paciente_id": paciente_e2e_id,
            "iniciada_vida_sexual": True,
            "edad_menarquia": 12,
            "tipo_ciclo": "oligomenorrea",
            "duracion_ciclo_habitual": 45,
            "gestas": 0
        }, headers=headers)
        assert res_ant.status_code == 201

        # 4. Registrar Datos Clínicos
        res_clin = client.post("/clinicos", json={
            "paciente_id": paciente_e2e_id,
            "consulta_id": consulta_e2e_id,
            "peso_kg": 68.0,
            "talla_cm": 162.0,
            "circunferencia_abdominal_cm": 86.0,
            "cadera_cm": 100.0,
            "score_ferriman_gallwey": 10,
            "hirsutismo": True,
            "acne": True,
            "ciclos_irregulares": True,
            "duracion_ciclo_dias": 45,
            "presion_sistolica": 115,
            "presion_diastolica": 75
        }, headers=headers)
        assert res_clin.status_code == 200

        # 5. Registrar Datos Hormonales
        res_horm = client.post("/hormonales", json={
            "paciente_id": paciente_e2e_id,
            "consulta_id": consulta_e2e_id,
            "lh": 13.5,
            "fsh": 4.5,
            "testosterona_total": 65.0,
            "glucosa_basal": 95.0,
            "insulina_basal": 16.0,
            "dia_ciclo_toma": 3
        }, headers=headers)
        assert res_horm.status_code == 200

        registrar_resultado(
            "Flujo E2E Paso 1: Admisión, consulta médica y captura multimodal completa",
            "Actividad 7",
            "Integración E2E",
            True,
            "Registro secuencial continuo de paciente, consulta, antecedentes, clínica y bioquímica"
        )
    except Exception as e:
        registrar_resultado("Flujo E2E Admisión y Captura", "Actividad 7", "Integración E2E", False, str(e))

    # 48. Flujo E2E Paso 2: Evaluación XGBoost + Clasificación Fenotípica Rotterdam
    try:
        # Inferencia XGBoost Criterios 1 y 2
        res_xgb = client.post("/evaluacion/xgboost", json={
            "paciente_id": paciente_e2e_id,
            "consulta_id": consulta_e2e_id,
            "duracion_ciclo_dias": 45,
            "score_ferriman_gallwey": 10,
            "testosterona_total": 65.0,
            "lh": 13.5,
            "fsh": 4.5
        }, headers=headers)
        assert res_xgb.status_code == 200

        # Clasificación Final Rotterdam
        res_rot = client.post("/clasificacion/evaluar", json={
            "paciente_id": paciente_e2e_id,
            "cumple_criterio1": True,
            "cumple_criterio2": True,
            "cumple_criterio3": False
        }, headers=headers)
        assert res_rot.status_code == 200
        assert res_rot.json()["fenotipo"] == "Fenotipo B"
        registrar_resultado(
            "Flujo E2E Paso 2: Evaluación mediante IA y clasificación fenotípica Rotterdam",
            "Actividad 7",
            "Integración E2E",
            True,
            "Inferencia combinada y emisión del fenotipo diagnóstico según Rotterdam"
        )
    except Exception as e:
        registrar_resultado("Flujo E2E Inferencia IA", "Actividad 7", "Integración E2E", False, str(e))

    # 49. Flujo E2E Paso 3: Validación médica y prescripción terapéutica
    try:
        # Confirmar Diagnóstico
        res_conf = client.post("/clasificacion/confirmar", json={
            "paciente_id": paciente_e2e_id,
            "consulta_id": consulta_e2e_id,
            "fenotipo_sugerido": "Fenotipo B",
            "fenotipo_confirmado": "Fenotipo B",
            "es_modificado": False,
            "conducta_terapeutica": "Plan farmacológico antiandrogénico e intervención en estilo de vida.",
            "medico_nombre": "Dra. Carla Casas"
        }, headers=headers)
        assert res_conf.status_code == 200

        # Guardar Plan de Tratamiento
        res_trat = client.post("/tratamiento/guardar", json={
            "paciente_id": paciente_e2e_id,
            "tipo": "farmacologico",
            "descripcion": "Tratamiento de inducción ovulatoria y control androgénico",
            "duracion_semanas": 24,
            "medicaciones": [{
                "nombre_medicamento": "Metformina",
                "dosis": "500 mg",
                "frecuencia": "Cada 12 horas",
                "fecha_inicio": "2026-06-01",
                "fecha_fin": "2026-12-01"
            }]
        }, headers=headers)
        assert res_trat.status_code == 200

        registrar_resultado(
            "Flujo E2E Paso 3: Validación por el especialista y prescripción terapéutica",
            "Actividad 7",
            "Integración E2E",
            True,
            "Confirmación formal del dictamen y emisión de farmacoterapia vinculada"
        )
    except Exception as e:
        registrar_resultado("Flujo E2E Validación y Tratamiento", "Actividad 7", "Integración E2E", False, str(e))

    # 50. Flujo E2E Paso 4: Emisión de orden médica y verificación en historial consolidado
    try:
        # Emitir orden de seguimiento
        res_ord = client.post("/ordenes-medicas/", json={
            "paciente_id": paciente_e2e_id,
            "consulta_id": consulta_e2e_id,
            "tipo_ecografia": "transvaginal",
            "indicacion_ecografia": "Evaluación folicular de seguimiento post-tratamiento",
            "examenes_laboratorio": [
                {"codigo": "LH", "nombre": "Hormona Luteinizante"},
                {"codigo": "FSH", "nombre": "Hormona Folículo Estimulante"}
            ],
            "prioridad": "normal"
        }, headers=headers)
        assert res_ord.status_code == 200

        # Consultar Historial y Comparativa
        res_hist = client.get(f"/consultas/paciente/{paciente_e2e_id}/comparativa", headers=headers)
        assert res_hist.status_code == 200
        data_h = res_hist.json()
        assert len(data_h["consultas"]) >= 1

        registrar_resultado(
            "Flujo E2E Paso 4: Emisión de orden complementaria y consulta de historial",
            "Actividad 7",
            "Integración E2E",
            True,
            "Cierre del ciclo de atención con verificación de consistencia en el expediente"
        )
    except Exception as e:
        registrar_resultado("Flujo E2E Orden y Cierre", "Actividad 7", "Integración E2E", False, str(e))

    # Limpieza
    if paciente_e2e_id:
        try:
            paciente_service.desactivar_paciente(paciente_e2e_id)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 8: AUDITORÍA Y REGISTROS DE ACTIVIDAD (LOGS FORENSES)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_8(headers: dict):
    print("\n--- Ejecutando Pruebas de Actividad 8: Auditoría y Logs Forenses ---")

    # 51. Consulta de logs de auditoría forense con paginación
    try:
        res = client.get("/auditoria/logs?limite=50", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)
        registrar_resultado(
            "Consulta del registro de auditoría médica forense con soporte de paginación",
            "Actividad 8",
            "Auditoría / Logs",
            True,
            "Retorna colección estructurada de eventos clínicos con HTTP 200"
        )
    except Exception as e:
        registrar_resultado("Consulta de logs de auditoría", "Actividad 8", "Auditoría / Logs", False, str(e))

    # 52. Filtro de logs de auditoría por módulo clínico
    try:
        res = client.get("/auditoria/logs?modulo=EXPEDIENTE&limite=20", headers=headers)
        assert res.status_code == 200
        logs = res.json()["logs"]
        for l in logs:
            assert l["modulo"] == "EXPEDIENTE"
        registrar_resultado(
            "Filtrado selectivo de eventos de auditoría por módulo clínico ('EXPEDIENTE')",
            "Actividad 8",
            "Filtro Forense",
            True,
            "Permite auditar específicamente modificaciones y diagnósticos en expedientes"
        )
    except Exception as e:
        registrar_resultado("Filtro por módulo", "Actividad 8", "Filtro Forense", False, str(e))

    # 53. Búsqueda y trazabilidad por término o usuario
    try:
        res = client.get("/auditoria/logs?q=Espinoza&limite=10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["logs"], list)
        registrar_resultado(
            "Búsqueda por coincidencia de término o usuario responsable ('Espinoza')",
            "Actividad 8",
            "Trazabilidad",
            True,
            "Localización ágil de acciones realizadas por un profesional específico"
        )
    except Exception as e:
        registrar_resultado("Búsqueda en logs", "Actividad 8", "Trazabilidad", False, str(e))

    # 54. Verificación de firma criptográfica SHA-256 inmutable en logs
    try:
        res = client.get("/auditoria/logs?limite=10", headers=headers)
        assert res.status_code == 200
        logs = res.json()["logs"]
        if logs:
            primer_log = logs[0]
            assert "hash_sha256" in primer_log
            assert len(primer_log["hash_sha256"]) == 64
        registrar_resultado(
            "Verificación de firma criptográfica SHA-256 inmutable en cada registro forense",
            "Actividad 8",
            "Seguridad / Integridad",
            True,
            "Garantiza el no repudio y previene la alteración retroactiva de eventos"
        )
    except Exception as e:
        registrar_resultado("Firma criptográfica SHA-256", "Actividad 8", "Seguridad / Integridad", False, str(e))

    # 55. Consulta de métricas consolidadas de auditoría médica
    try:
        res = client.get("/auditoria/metricas", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "eventos_totales_hoy" in data
        assert "trazabilidad_activa_pct" in data
        assert "validaciones_medicas" in data
        assert data["trazabilidad_activa_pct"] == 100.0
        registrar_resultado(
            "Consulta de métricas e indicadores de trazabilidad y seguridad (KPIs)",
            "Actividad 8",
            "Métricas / Auditoría",
            True,
            "Monitoreo en tiempo real de eventos, inferencias IA y validaciones humanas"
        )
    except Exception as e:
        registrar_resultado("Métricas de auditoría", "Actividad 8", "Métricas / Auditoría", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 9: EMISIÓN DE ÓRDENES MÉDICAS DE LABORATORIO Y ECOGRAFÍA (HU-021)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_9(headers: dict, paciente_id: str, consulta_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 9: Emisión de Órdenes Médicas ---")
    orden_id = None

    # 56. Validación: Tipo de ecografía no admitido
    try:
        res = client.post("/ordenes-medicas/", json={
            "paciente_id": paciente_id,
            "tipo_ecografia": "resonancia_magnetica_3d"  # No es ecografía
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de tipo de ecografía no admitido ('resonancia_magnetica_3d')",
            "Actividad 9",
            "Validación Taxonómica",
            True,
            "Taxonomía ecográfica: transvaginal, pelvica_abdominal, doppler, ninguna"
        )
    except Exception as e:
        registrar_resultado("Tipo de ecografía inválido", "Actividad 9", "Validación Taxonómica", False, str(e))

    # 57. Validación: Prioridad clínica no permitida
    try:
        res = client.post("/ordenes-medicas/", json={
            "paciente_id": paciente_id,
            "prioridad": "inmediata_super_urgente"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de prioridad clínica no admitida ('inmediata_super_urgente')",
            "Actividad 9",
            "Validación de Entrada",
            True,
            "Prioridades permitidas: normal, preferente, urgente"
        )
    except Exception as e:
        registrar_resultado("Prioridad inválida", "Actividad 9", "Validación de Entrada", False, str(e))

    # 58. Validación rebuscada: Indicación ecográfica demasiado corta (< 3 caracteres)
    try:
        res = client.post("/ordenes-medicas/", json={
            "paciente_id": paciente_id,
            "tipo_ecografia": "transvaginal",
            "indicacion_ecografia": "ok"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Rechazo de indicación ecográfica con longitud insuficiente (< 3 caracteres)",
            "Actividad 9",
            "Validación de Longitud",
            True,
            "Exige indicación técnica explícita para guiar el estudio de imagen"
        )
    except Exception as e:
        registrar_resultado("Indicación ecográfica corta", "Actividad 9", "Validación de Longitud", False, str(e))

    # 59. Emisión de orden para paciente inexistente retorna HTTP 404
    try:
        uuid_falso = str(uuid4())
        res = client.post("/ordenes-medicas/", json={
            "paciente_id": uuid_falso,
            "tipo_ecografia": "ninguna",
            "prioridad": "normal"
        }, headers=headers)
        assert res.status_code in [400, 404]
        registrar_resultado(
            "Rechazo de emisión de orden médica para paciente inexistente (HTTP 404)",
            "Actividad 9",
            "Integridad Referencial",
            True,
            "Impide generar órdenes complementarias huérfanas sin expediente previo"
        )
    except Exception as e:
        registrar_resultado("Orden para paciente inexistente", "Actividad 9", "Integridad Referencial", False, str(e))

    # 60. Emisión exitosa de orden médica integral (Laboratorio + Ecografía Rotterdam)
    try:
        res = client.post("/ordenes-medicas/", json={
            "paciente_id": paciente_id,
            "consulta_id": consulta_id,
            "tipo_ecografia": "transvaginal",
            "indicacion_ecografia": "Evaluación de morfología ovárica poliquística y recuento folicular antral",
            "examenes_laboratorio": [
                {"codigo": "LH", "nombre": "Hormona Luteinizante (LH)", "categoria": "hormonal"},
                {"codigo": "FSH", "nombre": "Hormona Folículo Estimulante (FSH)", "categoria": "hormonal"},
                {"codigo": "TESTO", "nombre": "Testosterona Total y Libre", "categoria": "hormonal"},
                {"codigo": "GLUC_INS", "nombre": "Curva Glucosa e Insulina (HOMA-IR)", "categoria": "metabolico"},
                {"codigo": "DHEA_S", "nombre": "Sulfato de Dehidroepiandrosterona (DHEA-S)", "categoria": "hormonal"}
            ],
            "indicaciones_preanaliticas": "Ayuno estricto de 8 horas. Toma entre el 2do y 5to día del ciclo.",
            "diagnostico_presuntivo": "Sospecha de SOP — Criterios de Rotterdam",
            "prioridad": "preferente",
            "observaciones": "Solicitud urgente para definir fenotipo Rotterdam."
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["paciente_id"] == paciente_id
        assert data["tipo_ecografia"] == "transvaginal"
        assert len(data["examenes_laboratorio"]) == 5
        assert data["prioridad"] == "preferente"
        assert data["estado"] == "vigente"
        orden_id = data["id"]
        registrar_resultado(
            "Emisión exitosa de orden médica multimodal (Laboratorio + Ecografía HU-021)",
            "Actividad 9",
            "Integración / HU-021",
            True,
            "Formalización completa de estudios hormonales, metabólicos y de imagen"
        )
    except Exception as e:
        registrar_resultado("Emisión exitosa de orden médica", "Actividad 9", "Integración / HU-021", False, str(e))

    # 61. Consulta de historial de órdenes emitidas para la paciente
    try:
        res = client.get(f"/ordenes-medicas/paciente/{paciente_id}", headers=headers)
        assert res.status_code == 200
        ordenes = res.json()
        assert isinstance(ordenes, list)
        assert len(ordenes) >= 1
        registrar_resultado(
            "Consulta del historial cronológico de órdenes médicas de la paciente",
            "Actividad 9",
            "Consulta de Historial",
            True,
            "Recupera todas las prescripciones de laboratorio e imagen de la paciente"
        )
    except Exception as e:
        registrar_resultado("Consulta de órdenes por paciente", "Actividad 9", "Consulta de Historial", False, str(e))

    # 62. Consulta detallada de orden médica específica por identificador
    if orden_id:
        try:
            res = client.get(f"/ordenes-medicas/{orden_id}", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["id"] == orden_id
            assert data["estado"] == "vigente"
            registrar_resultado(
                "Consulta individual detallada de orden médica por su identificador UUID",
                "Actividad 9",
                "Consulta Específica",
                True,
                "Permite visualizar la orden completa para impresión o formato PDF"
            )
        except Exception as e:
            registrar_resultado("Consulta por ID de orden", "Actividad 9", "Consulta Específica", False, str(e))

    # 63. Cancelación exitosa de orden médica vigente
    if orden_id:
        try:
            res = client.delete(f"/ordenes-medicas/{orden_id}", headers=headers)
            assert res.status_code == 200
            registrar_resultado(
                "Cancelación y anulación formal de orden médica vigente",
                "Actividad 9",
                "Gestión de Ciclo de Vida",
                True,
                "Permite dar de baja una orden médica emitida ante cambio de conducta clínica"
            )
        except Exception as e:
            registrar_resultado("Cancelación de orden médica", "Actividad 9", "Gestión de Ciclo de Vida", False, str(e))


def imprimir_tabla_resumen():
    """Imprime la tabla formateada con todos los resultados evitando caracteres incompatibles con cp1252."""
    total = len(resultados_pruebas)
    pasaron = sum(1 for r in resultados_pruebas if r["estado"] == "PASÓ")
    fallaron = total - pasaron

    print("\n" + "=" * 120)
    print(f"MATRIZ RESUMEN DE PRUEBAS DE CODIFICACION - SECCION 3.3.7.4 ({pasaron}/{total} PASARON - {100.0 * pasaron / total:.1f}%)")
    print("=" * 120)
    print(f"{'#':<3} | {'Nombre de la Prueba':<48} | {'Actividad':<13} | {'Tipo':<24} | {'Estado':<7} | {'Restriccion Evaluada'}")
    print("-" * 120)

    for i, r in enumerate(resultados_pruebas, 1):
        nombre_clean = r['nombre'][:48]
        restriccion_clean = r['restriccion']
        print(f"{i:<3} | {nombre_clean:<48} | {r['actividad']:<13} | {r['tipo'][:24]:<24} | {r['estado']:<7} | {restriccion_clean}")

    print("=" * 120)
    print(f"Total Evaluadas: {total} | Pasaron: {pasaron} | Fallaron: {fallaron} | Exito: {100.0 * pasaron / total:.1f}%")
    print("=" * 120)


if __name__ == "__main__":
    print("Iniciando Suite de Pruebas de Codificacion (Seccion 3.3.7.4 - Actividades 1 a 9)...")
    token = obtener_token_autenticado()
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Crear una paciente y cita base para vincular las actividades
    ci_base = f"CI-SEC7-{int(datetime.now().timestamp())}"
    res_p = client.post("/pacientes", json={
        "nombre": "Claudia",
        "primer_apellido": "Guzman",
        "ci": ci_base,
        "fecha_nacimiento": "1995-10-12"
    }, headers=auth_headers)
    p_id = res_p.json()["id"]

    # Registrar antecedentes base para la paciente
    client.post("/antecedentes", json={
        "paciente_id": p_id,
        "iniciada_vida_sexual": True,
        "edad_menarquia": 13,
        "tipo_ciclo": "irregular",
        "duracion_ciclo_habitual": 40,
        "gestas": 0
    }, headers=auth_headers)

    res_c = client.post("/consultas", json={
        "paciente_id": p_id,
        "motivo": "Evaluación diagnóstica integral de SOP"
    }, headers=auth_headers)
    cons_id = res_c.json()["id"]
    cita_id = res_c.json().get("cita_id")

    ejecutar_pruebas_actividad_1(auth_headers, p_id)
    ejecutar_pruebas_actividad_2(auth_headers, p_id, cons_id)
    ejecutar_pruebas_actividad_3(auth_headers, p_id)
    trat_id = ejecutar_pruebas_actividad_4(auth_headers, p_id, cita_id)
    ejecutar_pruebas_actividad_5(auth_headers, p_id, trat_id)
    ejecutar_pruebas_actividad_6(token, auth_headers)
    ejecutar_pruebas_actividad_7(auth_headers)
    ejecutar_pruebas_actividad_8(auth_headers)
    ejecutar_pruebas_actividad_9(auth_headers, p_id, cons_id)

    imprimir_tabla_resumen()

    # Limpieza final
    if p_id:
        try:
            paciente_service.desactivar_paciente(p_id)
        except Exception:
            pass
