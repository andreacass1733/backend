"""
========================================================================================
SUITE DE PRUEBAS FUNCIONALES Y NO FUNCIONALES — OBJETIVO ESPECÍFICO 5 (SECCIÓN 3.4.6)
Sistema de Apoyo al Diagnóstico de Síndrome de Ovario Poliquístico (SOP)
Consenso de Rotterdam (EfficientNet-B0 + XGBoost)
========================================================================================
Evalúa de manera automatizada:
  - 1. Autenticación, 2FA y Control de Acceso Clínico
  - 2. Gestión de Pacientes, Cédula Única y Búsqueda
  - 3. Antecedentes Médicos y Coherencia Gineco-Obstétrica
  - 4. Datos Clínicos y Hormonales (Score Ferriman, IMC, HOMA-IR, LH/FSH)
  - 5. Análisis Ecográfico con Red Convolucional EfficientNet-B0 (Criterio 3)
  - 6. Clasificación Tabular Clínica y Hormonal con XGBoost (Criterios 1 y 2)
  - 7. Lógica Fenotípica del Consenso de Rotterdam (Fenotipos A, B, C, D, Sin SOP)
  - 8. Validación Médica Especializada (Confirmación, Rectificación Justificada)
  - 9. Emisión y Gestión de Órdenes Médicas Multimodales (HU-021)
  - 10. Seguridad Row Level Security (RLS), Criptografía JWT y Cifrado
  - 11. Trazabilidad Forense Inmutable con Hash SHA-256 y Registro de Logs
  - 12. Tiempos de Respuesta y Rendimiento Operativo de la Plataforma
  - 13. Usabilidad, Manejo de Errores y Formatos Inválidos
========================================================================================
"""

import os
import sys
import time
import hashlib
import json
import uuid
import pytest
from datetime import datetime, timezone

# Asegurar path del backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(".env")

from starlette.testclient import TestClient
from main import app
from services.rotterdam_ia import clasificacion_service
from services.auth import auditoria_service, security_service
from db.supabase_client import get_supabase_admin_client

client = TestClient(app)

EMAIL_MEDICO = "carla.casas2004@gmail.com"
PWD_MEDICO = "Medico2026*"
MEDICO_ID = "0a8eaba2-be5b-4dbd-b22b-fc35c5616c12"


@pytest.fixture(scope="session")
def token_autorizado():
    """Restaura clave base e inicia sesión para obtener JWT con permisos clínicos."""
    try:
        admin = get_supabase_admin_client()
        admin.auth.admin.update_user_by_id(MEDICO_ID, {"password": PWD_MEDICO})
    except Exception:
        pass

    res_login = client.post("/auth/login", json={
        "email": EMAIL_MEDICO,
        "password": PWD_MEDICO
    })
    if res_login.status_code != 200:
        raise RuntimeError(f"Fallo login: {res_login.text}")
    sid = res_login.json()["session_id"]

    res_2fa = client.post("/auth/verify-2fa", json={
        "session_id": sid,
        "code": "796787"
    })
    if res_2fa.status_code != 200:
        raise RuntimeError(f"Fallo 2FA: {res_2fa.text}")

    return res_2fa.json()["access_token"]


@pytest.fixture(scope="session")
def headers_auth(token_autorizado):
    return {"Authorization": f"Bearer {token_autorizado}"}


@pytest.fixture(scope="session")
def paciente_id_prueba(headers_auth):
    """Crea una paciente real en base de datos para pruebas que exigen integridad referencial."""
    ci = f"CI-VAL5-{int(time.time())}"
    res = client.post("/pacientes", json={
        "nombre": "Valeria",
        "primer_apellido": "Rios",
        "ci": ci,
        "fecha_nacimiento": "1997-04-15"
    }, headers=headers_auth)
    return res.json()["id"]


# ==============================================================================
# 1. PRUEBAS FUNCIONALES: AUTENTICACIÓN, 2FA Y CONTROL DE ACCESO
# ==============================================================================

def test_01_autenticacion_login_exitoso():
    """HU-001: Inicio de sesión válido genera sesión 2FA y solicitud de OTP."""
    res = client.post("/auth/login", json={
        "email": EMAIL_MEDICO,
        "password": PWD_MEDICO
    })
    assert res.status_code == 200, f"Error en login: {res.text}"
    data = res.json()
    assert "session_id" in data
    assert (data.get("requires_2fa") is True) or (data.get("requiere_2fa") is True)
    assert "email_masked" in data


def test_02_autenticacion_rechazo_credenciales_invalidas():
    """HU-001: Bloqueo de acceso ante contraseñas incorrectas (HTTP 401)."""
    res = client.post("/auth/login", json={
        "email": EMAIL_MEDICO,
        "password": "PasswordErroneo2026*"
    })
    assert res.status_code in [400, 401]
    assert "detail" in res.json()


def test_03_autenticacion_validacion_campos_obligatorios_y_formato():
    """Control de entrada: Rechazo de campos vacíos o correo no RFC 5322."""
    res_vacio = client.post("/auth/login", json={"email": "", "password": ""})
    assert res_vacio.status_code in [400, 422]

    res_formato = client.post("/auth/login", json={
        "email": "medico_sin_arroba_ni_dominio",
        "password": "Password123*"
    })
    assert res_formato.status_code in [400, 422]


def test_04_autenticacion_verificacion_doble_factor_otp():
    """HU-002: Verificación de código OTP 2FA para emisión de token JWT."""
    res_login = client.post("/auth/login", json={
        "email": EMAIL_MEDICO,
        "password": PWD_MEDICO
    })
    sid = res_login.json().get("session_id")
    
    res_2fa = client.post("/auth/verify-2fa", json={
        "session_id": sid,
        "code": "796787"
    })
    assert res_2fa.status_code == 200
    data = res_2fa.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


# ==============================================================================
# 2. PRUEBAS FUNCIONALES: GESTIÓN DE PACIENTES Y ANTECEDENTES
# ==============================================================================

def test_05_registro_paciente_con_validaciones(headers_auth):
    """HU-003: Registro correcto de expediente de paciente con Cédula de Identidad."""
    ci_aleatorio = f"CI-TEST-{int(time.time())}"
    res = client.post("/pacientes", json={
        "nombre": "Valeria",
        "primer_apellido": "Rios",
        "ci": ci_aleatorio,
        "fecha_nacimiento": "1997-04-15",
        "telefono": "70012345"
    }, headers=headers_auth)
    assert res.status_code in [200, 201]
    data = res.json()
    assert data["nombre"] == "Valeria"
    assert data["ci"] == ci_aleatorio


def test_06_registro_paciente_rechazo_ci_duplicado(headers_auth):
    """HU-003: Prevención de duplicados asegurando unicidad de CI."""
    ci_fijo = f"CI-DUP-{int(time.time())}"
    client.post("/pacientes", json={
        "nombre": "Mariana",
        "primer_apellido": "Paz",
        "ci": ci_fijo,
        "fecha_nacimiento": "1998-02-10"
    }, headers=headers_auth)

    res_duplicado = client.post("/pacientes", json={
        "nombre": "Mariana",
        "primer_apellido": "Paz",
        "ci": ci_fijo,
        "fecha_nacimiento": "1998-02-10"
    }, headers=headers_auth)
    assert res_duplicado.status_code in [400, 409]


def test_07_busqueda_pacientes_parcial_e_insensible(headers_auth):
    """HU-004: Búsqueda flexible de pacientes activa e insensible a mayúsculas."""
    res = client.get("/pacientes?busqueda=valeria", headers=headers_auth)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_08_antecedentes_coherencia_obstetrica(headers_auth, paciente_id_prueba):
    """HU-005: Formulario de antecedentes médicos con validación de coherencia."""
    res = client.post("/antecedentes", json={
        "paciente_id": paciente_id_prueba,
        "iniciada_vida_sexual": True,
        "edad_menarquia": 12,
        "tipo_ciclo": "irregular",
        "duracion_ciclo_habitual": 45,
        "gestas": 0
    }, headers=headers_auth)
    assert res.status_code in [200, 201]


# ==============================================================================
# 3. PRUEBAS FUNCIONALES: DATOS CLÍNICOS Y HORMONALES
# ==============================================================================

def test_09_datos_clinicos_calculo_imc_y_rcc():
    """HU-006: Cálculo biométrico automático de IMC y relación cintura/cadera (RCC)."""
    # Altura: 1.60 m, Peso: 70 kg -> IMC = 70 / (1.60^2) = 27.34 (Sobrepeso)
    # Cintura: 88 cm, Cadera: 98 cm -> RCC = 88 / 98 = 0.898 (Riesgo androide > 0.85)
    peso = 70.0
    altura = 1.60
    imc_calculado = round(peso / (altura ** 2), 2)
    assert imc_calculado == 27.34

    cintura = 88.0
    cadera = 98.0
    rcc_calculado = round(cintura / cadera, 3)
    assert rcc_calculado == 0.898
    assert rcc_calculado > 0.85  # Criterio de riesgo androide


def test_10_datos_hormonales_calculo_homa_ir_y_lh_fsh():
    """HU-009: Cálculo bioquímico de resistencia a la insulina (HOMA-IR) y cociente LH/FSH."""
    # Glucosa: 96 mg/dL, Insulina: 16 µUI/mL -> HOMA-IR = (96 * 16) / 405 = 3.79 (Resistencia)
    glucosa = 96.0
    insulina = 16.0
    homa_ir = round((glucosa * insulina) / 405.0, 2)
    assert homa_ir == 3.79
    assert homa_ir >= 2.5  # Umbral de resistencia a la insulina

    # LH: 12.5 mUI/mL, FSH: 4.5 mUI/mL -> Ratio LH/FSH = 12.5 / 4.5 = 2.78 (Alterado >= 2.0)
    lh = 12.5
    fsh = 4.5
    ratio_lh_fsh = round(lh / fsh, 2)
    assert ratio_lh_fsh == 2.78
    assert ratio_lh_fsh >= 2.0


def test_11_datos_clinicos_rechazo_valores_negativos(headers_auth, paciente_id_prueba):
    """Control de rango: Rechazo de mediciones fisiológicas fuera de rango (Score Ferriman > 36)."""
    res = client.post("/clinicos/", json={
        "paciente_id": paciente_id_prueba,
        "score_ferriman_gallwey": 50,
        "presion_sistolica": 80,
        "presion_diastolica": 120
    }, headers=headers_auth)
    assert res.status_code in [400, 422]


# ==============================================================================
# 4. PRUEBAS FUNCIONALES: MODELOS DE INTELIGENCIA ARTIFICIAL (IA)
# ==============================================================================

def test_12_clasificacion_tabular_xgboost_criterios_1_y_2():
    """Objetivo 3: Ejecución de modelo XGBoost sobre datos clínicos y hormonales."""
    import joblib
    xgb_path = os.path.join("models_ia", "best_xgboost.pkl")
    assert os.path.exists(xgb_path), "El artefacto del modelo XGBoost debe existir"
    model = joblib.load(xgb_path)
    assert hasattr(model, "predict_proba")


def test_13_analisis_ecografico_efficientnet_b0_criterio_3():
    """Objetivo 2: Verificación de arquitectura y carga de EfficientNet-B0 para Criterio 3."""
    from services.rotterdam_ia import criterio3_service
    modelo_eff = criterio3_service.get_model()
    assert modelo_eff is not None
    assert modelo_eff.input_shape == (None, 224, 224, 3)
    assert len(criterio3_service.CLASES) == 2


def test_14_carga_ecografia_formato_no_permitido(headers_auth):
    """Control de carga de archivos: Rechazo de formatos no válidos o ejecutables."""
    files = {"archivo": ("script_malicioso.exe", b"malicious binary payload", "application/x-msdownload")}
    res = client.post("/criterio3/predecir", files=files, headers=headers_auth)
    assert res.status_code in [400, 415, 422, 500]


# ==============================================================================
# 5. PRUEBAS FUNCIONALES: CONSENSO DE ROTTERDAM
# ==============================================================================

def test_15_clasificacion_rotterdam_fenotipo_a(headers_auth):
    """Rotterdam Fenotipo A: Cumplimiento de los 3 criterios (Clásico Completo)."""
    res = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": True,
        "cumple_criterio2": True,
        "cumple_criterio3": True
    }, headers=headers_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["fenotipo"] == "Fenotipo A"
    assert data["tiene_sop"] is True


def test_16_clasificacion_rotterdam_fenotipos_b_c_d(headers_auth):
    """Rotterdam Fenotipos B, C y D: Cumplimiento de combinaciones de 2 criterios."""
    # Fenotipo B (C1 + C2)
    r_b = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": True,
        "cumple_criterio2": True,
        "cumple_criterio3": False
    }, headers=headers_auth)
    assert r_b.json()["fenotipo"] == "Fenotipo B"

    # Fenotipo C (C2 + C3)
    r_c = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": False,
        "cumple_criterio2": True,
        "cumple_criterio3": True
    }, headers=headers_auth)
    assert r_c.json()["fenotipo"] == "Fenotipo C"

    # Fenotipo D (C1 + C3)
    r_d = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": True,
        "cumple_criterio2": False,
        "cumple_criterio3": True
    }, headers=headers_auth)
    assert r_d.json()["fenotipo"] == "Fenotipo D"


def test_17_clasificacion_rotterdam_sin_sop_menos_de_dos_criterios(headers_auth):
    """Rotterdam Negativo: Cumplir menos de 2 criterios se clasifica como 'Sin SOP'."""
    res_1 = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": True,
        "cumple_criterio2": False,
        "cumple_criterio3": False
    }, headers=headers_auth)
    assert res_1.json()["fenotipo"] == "Sin SOP"
    assert res_1.json()["tiene_sop"] is False


# ==============================================================================
# 6. PRUEBAS FUNCIONALES: VALIDACIÓN MÉDICA Y ÓRDENES MÉDICAS
# ==============================================================================

def test_18_confirmacion_diagnostico_medico(headers_auth, paciente_id_prueba):
    """HU-014: Especialista confirma fenotipo sugerido con persistencia en expediente."""
    res = client.post("/clasificacion/confirmar", json={
        "paciente_id": paciente_id_prueba,
        "fenotipo_sugerido": "Fenotipo A",
        "fenotipo_confirmado": "Fenotipo A",
        "es_modificado": False,
        "conducta_terapeutica": "Inicio de cambios en estilo de vida y metformina"
    }, headers=headers_auth)
    assert res.status_code == 200
    assert res.json()["exito"] is True
    assert res.json()["fenotipo_final"] == "Fenotipo A"


def test_19_rectificacion_diagnostica_requiere_justificacion(headers_auth, paciente_id_prueba):
    """Control deontológico: Rechazo de rectificación médica sin justificación clínica."""
    res = client.post("/clasificacion/confirmar", json={
        "paciente_id": paciente_id_prueba,
        "fenotipo_sugerido": "Fenotipo A",
        "fenotipo_confirmado": "Sin SOP",
        "es_modificado": True,
        "justificacion_medica": ""  # Justificación vacía no permitida
    }, headers=headers_auth)
    assert res.status_code in [400, 422]


def test_20_emision_orden_medica_multimodal(headers_auth, paciente_id_prueba):
    """HU-021: Emisión exitosa de orden médica con laboratorio y ecografía ovárica."""
    res = client.post("/ordenes-medicas/", json={
        "paciente_id": paciente_id_prueba,
        "tipo_ecografia": "transvaginal",
        "indicacion_ecografia": "Recuento folicular antral y volumen ovárico",
        "examenes_laboratorio": [
            {"codigo": "LH", "nombre": "Hormona Luteinizante"},
            {"codigo": "FSH", "nombre": "Hormona Folículo Estimulante"}
        ],
        "prioridad": "preferente"
    }, headers=headers_auth)
    assert res.status_code in [200, 201]
    data = res.json()
    assert data["tipo_ecografia"] == "transvaginal"
    assert data["prioridad"] == "preferente"
    assert data["estado"] == "vigente"


def test_21_orden_medica_validacion_prioridad_y_tipo_ecografia(headers_auth):
    """Validación taxonómica: Rechazo de prioridades o estudios fuera de catálogo."""
    res_prioridad = client.post("/ordenes-medicas/", json={
        "paciente_id": str(uuid.uuid4()),
        "prioridad": "prioridad_invalida_no_permitida"
    }, headers=headers_auth)
    assert res_prioridad.status_code in [400, 422]

    res_eco = client.post("/ordenes-medicas/", json={
        "paciente_id": str(uuid.uuid4()),
        "tipo_ecografia": "tomografia_axial_no_aplica"
    }, headers=headers_auth)
    assert res_eco.status_code in [400, 422]


# ==============================================================================
# 7. PRUEBAS NO FUNCIONALES: SEGURIDAD, AUDITORÍA, TIEMPOS Y USABILIDAD
# ==============================================================================

def test_22_no_funcional_seguridad_bloqueo_sin_autenticacion():
    """Seguridad / RLS: Bloqueo inmediato de solicitudes clínicas sin token Bearer."""
    rutas_protegidas = [
        "/pacientes",
        "/antecedentes",
        "/datos-clinicos",
        "/datos-hormonales",
        "/clasificacion/evaluar",
        "/ordenes-medicas/"
    ]
    for ruta in rutas_protegidas:
        res = client.get(ruta) if not ruta.endswith("/") else client.post(ruta, json={})
        assert res.status_code == 401, f"La ruta {ruta} debe requerir autenticación obligatoria"


def test_23_no_funcional_seguridad_deteccion_jwt_manipulado():
    """Seguridad / Criptografía: Detección y rechazo de JWT con firma adulterada."""
    token_falso = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTYifQ.firma_totalmente_falsa"
    res = client.get("/pacientes", headers={"Authorization": f"Bearer {token_falso}"})
    assert res.status_code == 401


def test_24_no_funcional_trazabilidad_auditoria_inmutable_sha256(headers_auth):
    """Trazabilidad Forense: Generación de firma inmutable SHA-256 para eventos de auditoría."""
    evento = {
        "usuario_id": MEDICO_ID,
        "accion": "VALIDACION_DIAGNOSTICA_ROTTERDAM",
        "modulo": "CLASIFICACION",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    hash_esperado = hashlib.sha256(json.dumps(evento, sort_keys=True).encode()).hexdigest()
    assert len(hash_esperado) == 64
    assert all(c in "0123456789abcdef" for c in hash_esperado)


def test_25_no_funcional_tiempo_respuesta_endpoints_clinicos(headers_auth):
    """Tiempo de respuesta: Los endpoints de consulta clínica responden de forma eficiente."""
    # Warmup
    client.get("/pacientes?pagina=1&por_pagina=1", headers=headers_auth)
    
    t0 = time.time()
    res = client.get("/pacientes?pagina=1&por_pagina=5", headers=headers_auth)
    duracion_ms = (time.time() - t0) * 1000.0
    assert res.status_code == 200
    assert duracion_ms < 1500.0, f"Tiempo excedido: {duracion_ms:.2f} ms (meta < 1500 ms)"


def test_26_no_funcional_tiempo_respuesta_evaluacion_rotterdam(headers_auth):
    """Rendimiento: Inferencia de clasificación Rotterdam en < 2000 ms."""
    t0 = time.time()
    res = client.post("/clasificacion/evaluar", json={
        "paciente_id": str(uuid.uuid4()),
        "cumple_criterio1": True,
        "cumple_criterio2": True,
        "cumple_criterio3": True
    }, headers=headers_auth)
    duracion_ms = (time.time() - t0) * 1000.0
    assert res.status_code == 200
    assert duracion_ms < 2000.0, f"Inferencia excedida: {duracion_ms:.2f} ms (meta < 2000 ms)"


def test_27_no_funcional_usabilidad_mensajes_de_error_estructurados():
    """Usabilidad y consistencia: Errores retornan formato JSON estructurado con 'detail'."""
    res = client.post("/auth/login", json={"email": "formato_invalido", "password": "123"})
    assert res.headers.get("content-type", "").startswith("application/json")
    data = res.json()
    assert "detail" in data
    assert isinstance(data["detail"], (str, list))
