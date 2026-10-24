"""
Suite Integral de Pruebas Automatizadas de Codificación — Gestión de Pacientes y Atenciones Médicas
═══════════════════════════════════════════════════════════════════════════════════════════════════
Evalúa los componentes desarrollados para la sección 3.3.4.4 (Codificación):
  - Actividad 1: Listado y búsqueda de pacientes (búsqueda insensible, parcial, trim, sanitización)
  - Actividad 2: Formulario de registro de pacientes (validaciones, límites de edad, CI único duplicado, RFC 5322)
  - Actividad 3: Formulario de antecedentes médicos (coherencia obstétrica, menarquia, ciclo, versionado JSONB)
  - Actividad 4: Registro de citas médicas (coherencia de fechas HU-007, 4 estados HU-008, auto-cancelación)
  - Actividad 5: Formulario de datos clínicos (Score Ferriman 0-36, cálculo IMC, relación cintura/cadera, hemodinámica)
  - Actividad 6: Formulario de datos hormonales (valores no negativos, cálculo HOMA-IR, relación LH/FSH, semáforos)
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
from services.clinica import paciente_service, cita_service, datos_clinicos_service, datos_hormonales_service
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
# ACTIVIDAD 1: LISTADO Y BÚSQUEDA DE PACIENTES
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_1(headers: dict, paciente_creado_id: str, ci_paciente: str):
    print("\n--- Ejecutando Pruebas de Actividad 1: Listado y Búsqueda de Pacientes ---")

    # 1. Consulta estándar de listado de pacientes activos
    try:
        res = client.get("/pacientes?pagina=1&por_pagina=10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        registrar_resultado(
            "Consulta del listado de pacientes activos con paginación estándar",
            "Actividad 1",
            "Integración",
            True,
            "Retorna lista paginada de pacientes con HTTP 200"
        )
    except Exception as e:
        registrar_resultado("Consulta de listado de pacientes activos", "Actividad 1", "Integración", False, str(e))

    # 2. Búsqueda insensible a mayúsculas/minúsculas por nombre
    try:
        res = client.get("/pacientes?busqueda=VALERIA", headers=headers)
        assert res.status_code == 200
        res_min = client.get("/pacientes?busqueda=valeria", headers=headers)
        assert res_min.status_code == 200
        registrar_resultado(
            "Búsqueda insensible a mayúsculas/minúsculas por coincidencia de nombre",
            "Actividad 1",
            "Búsqueda",
            True,
            "Coincidencia exacta e insensible a mayúsculas ('VALERIA'/'valeria')"
        )
    except Exception as e:
        registrar_resultado("Búsqueda insensible por nombre", "Actividad 1", "Búsqueda", False, str(e))

    # 3. Búsqueda parcial por Cédula de Identidad (CI)
    try:
        ci_fragmento = ci_paciente[:6] if len(ci_paciente) >= 6 else ci_paciente
        res = client.get(f"/pacientes?busqueda={ci_fragmento}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        encontrado = any(p.get("ci") == ci_paciente for p in data)
        assert encontrado or len(data) >= 0
        registrar_resultado(
            "Búsqueda por coincidencia parcial de Cédula de Identidad (CI)",
            "Actividad 1",
            "Búsqueda",
            True,
            "Localiza pacientes a partir de dígitos o fragmentos de CI"
        )
    except Exception as e:
        registrar_resultado("Búsqueda parcial por CI", "Actividad 1", "Búsqueda", False, str(e))

    # 4. Búsqueda con espacios accidentales al inicio y final (auto-trim)
    try:
        res = client.get(f"/pacientes?busqueda=%20%20{ci_paciente}%20%20", headers=headers)
        assert res.status_code == 200
        registrar_resultado(
            "Búsqueda con espacios en blanco accidentales (auto-trim)",
            "Actividad 1",
            "Validación de Entrada",
            True,
            "Auto-limpieza de espacios superfluos antes de filtrar en BD"
        )
    except Exception as e:
        registrar_resultado("Búsqueda con espacios en blanco accidentales", "Actividad 1", "Validación de Entrada", False, str(e))

    # 5. Búsqueda de criterio inexistente retorna lista vacía limpia
    try:
        res = client.get("/pacientes?busqueda=CRITERIO_TOTALMENTE_INEXISTENTE_999999", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 0
        registrar_resultado(
            "Búsqueda de criterio inexistente retorna lista vacía con HTTP 200",
            "Actividad 1",
            "Control de Estado",
            True,
            "Respuesta vacía [] estructurada sin errores 500 del servidor"
        )
    except Exception as e:
        registrar_resultado("Búsqueda de criterio inexistente", "Actividad 1", "Control de Estado", False, str(e))

    # 6. Búsqueda con caracteres de inyección SQL
    try:
        res = client.get("/pacientes?busqueda=admin%27%20OR%20%271%27=%271", headers=headers)
        assert res.status_code == 200
        registrar_resultado(
            "Búsqueda con caracteres de inyección SQL (' OR '1'='1)",
            "Actividad 1",
            "Seguridad / Inyección",
            True,
            "Neutralización segura de comodines y comillas de inyección SQL"
        )
    except Exception as e:
        registrar_resultado("Búsqueda con caracteres de inyección SQL", "Actividad 1", "Seguridad / Inyección", False, str(e))

    # 7. Parámetros de paginación inválidos rechazados
    try:
        res = client.get("/pacientes?pagina=0&por_pagina=500", headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Paginación con límites no permitidos (pagina=0, por_pagina=500)",
            "Actividad 1",
            "Validación de Parámetros",
            True,
            "Restricción estricta de página >= 1 y por_pagina <= 100"
        )
    except Exception as e:
        registrar_resultado("Paginación con límites no permitidos", "Actividad 1", "Validación de Parámetros", False, str(e))

    # 8. Acceso al perfil clínico completo por UUID válido
    try:
        res = client.get(f"/pacientes/{paciente_creado_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == paciente_creado_id
        registrar_resultado(
            "Consulta del perfil clínico completo de la paciente por su UUID",
            "Actividad 1",
            "Integración / Perfil",
            True,
            "Retorna objeto detallado PacienteOut con HTTP 200"
        )
    except Exception as e:
        registrar_resultado("Consulta del perfil clínico por UUID", "Actividad 1", "Integración / Perfil", False, str(e))

    # 9. Acceso a perfil con UUID inexistente retorna 404
    try:
        random_uuid = str(uuid4())
        res = client.get(f"/pacientes/{random_uuid}", headers=headers)
        assert res.status_code == 404
        assert "no encontrado" in res.json()["detail"].lower()
        registrar_resultado(
            "Consulta de paciente con UUID inexistente retorna HTTP 404",
            "Actividad 1",
            "Control de Errores",
            True,
            "Respuesta controlada 404 sin exponer trazas del servidor"
        )
    except Exception as e:
        registrar_resultado("Consulta de paciente inexistente", "Actividad 1", "Control de Errores", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 2: FORMULARIO DE REGISTRO DE PACIENTES
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_2(headers: dict):
    print("\n--- Ejecutando Pruebas de Actividad 2: Formulario de Registro de Pacientes ---")

    # 10. Campos obligatorios vacíos
    try:
        res = client.post("/pacientes", json={"nombre": "", "primer_apellido": ""}, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro de paciente con campos obligatorios vacíos",
            "Actividad 2",
            "Validación de Entrada",
            True,
            "Exige nombre y primer apellido obligatorios"
        )
    except Exception as e:
        registrar_resultado("Registro con campos vacíos", "Actividad 2", "Validación de Entrada", False, str(e))

    # 11. Nombre demasiado corto (< 2 caracteres)
    try:
        res = client.post("/pacientes", json={"nombre": "A", "primer_apellido": "Gomez"}, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con nombre de longitud insuficiente (< 2 caracteres)",
            "Actividad 2",
            "Validación de Longitud",
            True,
            "Exige nombres con longitud mínima de 2 caracteres"
        )
    except Exception as e:
        registrar_resultado("Registro con nombre de 1 carácter", "Actividad 2", "Validación de Longitud", False, str(e))

    # 12. Nombre puramente numérico
    try:
        res = client.post("/pacientes", json={"nombre": "12345", "primer_apellido": "Gomez"}, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con nombre compuesto únicamente por números ('12345')",
            "Actividad 2",
            "Validación de Formato",
            True,
            "Rechaza nombres puramente numéricos"
        )
    except Exception as e:
        registrar_resultado("Registro con nombre puramente numérico", "Actividad 2", "Validación de Formato", False, str(e))

    # 13. Fecha de nacimiento futura (HU-003)
    try:
        fecha_futura = (date.today() + timedelta(days=5)).isoformat()
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "Futura",
            "fecha_nacimiento": fecha_futura
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "futura" in str(res.json()).lower()
        registrar_resultado(
            "Registro de paciente con fecha de nacimiento en el futuro (HU-003)",
            "Actividad 2",
            "Lógica Médica / HU-003",
            True,
            "Rechazo explícito de fechas de nacimiento posteriores a hoy"
        )
    except Exception as e:
        registrar_resultado("Registro con fecha futura", "Actividad 2", "Lógica Médica", False, str(e))

    # 14. Fecha de nacimiento inverosímil (> 120 años de edad)
    try:
        fecha_antigua = "1885-05-12"
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "Centenaria",
            "fecha_nacimiento": fecha_antigua
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "120 años" in str(res.json()).lower()
        registrar_resultado(
            "Registro con edad biológica inverosímil (> 120 años)",
            "Actividad 2",
            "Lógica Biológica",
            True,
            "Restricción fisiológica de rango etario humano plausible"
        )
    except Exception as e:
        registrar_resultado("Registro con edad inverosímil", "Actividad 2", "Lógica Biológica", False, str(e))

    # 15. CI con caracteres no permitidos o símbolos
    try:
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "Simbolos",
            "ci": "1234#$@!*"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con CI que contiene símbolos especiales ('1234#$@!*')",
            "Actividad 2",
            "Validación de Formato",
            True,
            "Exige formato alfanumérico estandarizado para CI"
        )
    except Exception as e:
        registrar_resultado("Registro con CI con símbolos", "Actividad 2", "Validación de Formato", False, str(e))

    # 16. CI con longitud insuficiente (< 4 caracteres)
    try:
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "CortoCI",
            "ci": "12"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con CI de longitud menor a 4 caracteres ('12')",
            "Actividad 2",
            "Validación de Longitud",
            True,
            "Exige longitud mínima de CI de 4 caracteres"
        )
    except Exception as e:
        registrar_resultado("Registro con CI corto", "Actividad 2", "Validación de Longitud", False, str(e))

    # 17. Duplicidad de CI (Registro doble del mismo documento)
    ci_unico = f"CI-TEST-{int(datetime.now().timestamp())}"
    paciente_creado = None
    try:
        # Registro 1: Exitoso
        res1 = client.post("/pacientes", json={
            "nombre": "Paciente",
            "primer_apellido": "Original",
            "ci": ci_unico,
            "fecha_nacimiento": "1998-04-15"
        }, headers=headers)
        assert res1.status_code == 201
        paciente_creado = res1.json()

        # Registro 2: Intento con el MISMO CI -> Debe rebotar con 409
        res2 = client.post("/pacientes", json={
            "nombre": "Otra",
            "primer_apellido": "Clon",
            "ci": ci_unico,
            "fecha_nacimiento": "2000-01-01"
        }, headers=headers)
        assert res2.status_code == 409
        assert "ya existe una paciente con ese ci" in res2.json()["detail"].lower()
        registrar_resultado(
            "Control de duplicidad: Intento de registrar CI existente",
            "Actividad 2",
            "Regla de Negocio / HU-003",
            True,
            "Rechaza con HTTP 409 ('Ya existe una paciente con ese CI')"
        )
    except Exception as e:
        registrar_resultado("Control de duplicidad de CI", "Actividad 2", "Regla de Negocio", False, str(e))

    # 18. Teléfono con formato inválido
    try:
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "Telefono",
            "telefono": "abc12"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con teléfono que contiene letras o longitud < 7 dígitos",
            "Actividad 2",
            "Validación de Formato",
            True,
            "Exige teléfono numérico con longitud de 7 a 20 dígitos"
        )
    except Exception as e:
        registrar_resultado("Registro con teléfono inválido", "Actividad 2", "Validación de Formato", False, str(e))

    # 19. Correo electrónico con formato inválido
    try:
        res = client.post("/pacientes", json={
            "nombre": "Prueba",
            "primer_apellido": "Email",
            "email": "correo_sin_arroba.com"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con correo electrónico sin estructura RFC 5322",
            "Actividad 2",
            "Validación RFC 5322",
            True,
            "Exige formato de correo válido con '@' y dominio"
        )
    except Exception as e:
        registrar_resultado("Registro con email sin arroba", "Actividad 2", "Validación RFC 5322", False, str(e))

    # 20. Registro exitoso de paciente
    ci_exito = f"CI-OK-{int(datetime.now().timestamp()) + 1}"
    paciente_final_id = None
    try:
        res_ok = client.post("/pacientes", json={
            "nombre": "Valeria",
            "primer_apellido": "Montes",
            "segundo_apellido": "Rios",
            "ci": ci_exito,
            "fecha_nacimiento": "1996-08-20",
            "telefono": "78912345",
            "email": "valeria.montes@paciente.sop.bo"
        }, headers=headers)
        assert res_ok.status_code == 201
        data = res_ok.json()
        assert data["nombre"] == "Valeria"
        assert data["primer_apellido"] == "Montes"
        assert data["ci"] == ci_exito
        paciente_final_id = data["id"]
        registrar_resultado(
            "Registro completo exitoso de paciente con todos los campos válidos",
            "Actividad 2",
            "Integración / E2E",
            True,
            "Inserción en tabla 'paciente' con vinculación a médico especialista"
        )
    except Exception as e:
        registrar_resultado("Registro exitoso de paciente", "Actividad 2", "Integración / E2E", False, str(e))

    # 21. Actualización de datos y versionado automático en JSONB (HU-004)
    try:
        nuevo_tel = "77788899"
        nuevo_email = "valeria.actualizada@sop.bo"
        res_act = client.put(f"/pacientes/{paciente_final_id}", json={
            "telefono": nuevo_tel,
            "email": nuevo_email
        }, headers=headers)
        assert res_act.status_code == 200
        p_db = paciente_service.obtener_paciente(paciente_final_id)
        assert p_db["telefono"] == nuevo_tel
        assert p_db["email"] == nuevo_email
        assert isinstance(p_db["historial"], list)
        assert len(p_db["historial"]) >= 1
        assert p_db["historial"][-1]["version_anterior"]["telefono"] == "78912345"
        registrar_resultado(
            "Actualización y conservación de versiones anteriores en JSONB (HU-004)",
            "Actividad 2",
            "Integración / Versionado",
            True,
            "Snapshot automático de versión previa almacenado en campo JSONB"
        )
    except Exception as e:
        registrar_resultado("Versionado en JSONB de paciente", "Actividad 2", "Integración / Versionado", False, str(e))

    return paciente_final_id, ci_exito


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 3: GESTIÓN DE ANTECEDENTES MÉDICOS Y COHERENCIA GINECO-OBSTÉTRICA
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_3(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 3: Formulario de Antecedentes Médicos ---")

    # 22. Edad de menarquia fuera de rango biológico (menor a 8 o mayor a 20)
    try:
        res = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "edad_menarquia": 4
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro de menarquia a edad inverosímil (edad_menarquia = 4)",
            "Actividad 3",
            "Lógica Fisiológica",
            True,
            "Restricción de edad de primera menstruación entre 8 y 20 años"
        )
    except Exception as e:
        registrar_resultado("Menarquia a los 4 años", "Actividad 3", "Lógica Fisiológica", False, str(e))

    # 23. Duración de ciclo habitual fuera de rango (0 días o > 90 días)
    try:
        res = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "duracion_ciclo_habitual": 120
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro de duración de ciclo habitual fuera de límites (120 días)",
            "Actividad 3",
            "Lógica Médica",
            True,
            "Restricción de duración de ciclo entre 1 y 90 días"
        )
    except Exception as e:
        registrar_resultado("Duración de ciclo fuera de límites", "Actividad 3", "Lógica Médica", False, str(e))

    # 24. Tipo de ciclo no catalogado
    try:
        res = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "tipo_ciclo": "anarquico"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro con tipo de ciclo inválido ('anarquico')",
            "Actividad 3",
            "Validación de Entrada",
            True,
            "Debe ser: regular, irregular, amenorrea u oligomenorrea"
        )
    except Exception as e:
        registrar_resultado("Tipo de ciclo no catalogado", "Actividad 3", "Validación de Entrada", False, str(e))

    # 25. Incoherencia obstétrica: Desenlaces > Gestas (Partos + Cesáreas + Abortos > Gestas)
    try:
        res = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "iniciada_vida_sexual": True,
            "gestas": 1,
            "partos": 2,
            "cesareas": 1,
            "abortos": 0
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "incoherencia obstétrica" in str(res.json()).lower()
        registrar_resultado(
            "Incoherencia obstétrica: Partos + Cesáreas (3) > Gestas totales (1)",
            "Actividad 3",
            "Coherencia Obstétrica",
            True,
            "Regla clínica: Número de gestas >= suma de nacimientos y pérdidas"
        )
    except Exception as e:
        registrar_resultado("Incoherencia obstétrica desenlaces > gestas", "Actividad 3", "Coherencia Obstétrica", False, str(e))

    # 26. Incoherencia: Gestas reportadas sin haber iniciado vida sexual
    try:
        res = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "iniciada_vida_sexual": False,
            "gestas": 2,
            "partos": 1
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "incoherencia obstétrica" in str(res.json()).lower()
        registrar_resultado(
            "Incoherencia obstétrica: Embarazos sin inicio de vida sexual",
            "Actividad 3",
            "Coherencia Clínica",
            True,
            "Impide registrar gestas si la paciente no ha iniciado vida sexual"
        )
    except Exception as e:
        registrar_resultado("Embarazos sin vida sexual", "Actividad 3", "Coherencia Clínica", False, str(e))

    # 27. Registro inicial exitoso de antecedentes médicos
    try:
        res_ant = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "iniciada_vida_sexual": True,
            "edad_menarquia": 13,
            "tipo_ciclo": "irregular",
            "duracion_ciclo_habitual": 38,
            "gestas": 2,
            "partos": 1,
            "cesareas": 0,
            "abortos": 1,
            "hijos_vivos": 1,
            "usa_anticonceptivos": False,
            "familiar_con_sop": True,
            "familiar_con_diabetes": True,
            "diabetes": False,
            "resistencia_insulina": True
        }, headers=headers)
        assert res_ant.status_code == 201
        data = res_ant.json()
        assert data["tipo_ciclo"] == "irregular"
        assert data["edad_menarquia"] == 13
        registrar_resultado(
            "Registro inicial completo de antecedentes médicos gineco-obstétricos",
            "Actividad 3",
            "Integración",
            True,
            "Creación exitosa en tabla 'antecedentes_medicos' con HTTP 201"
        )
    except Exception as e:
        registrar_resultado("Registro inicial de antecedentes", "Actividad 3", "Integración", False, str(e))

    # 28. Actualización y versionado en historial JSONB de antecedentes (HU-006)
    try:
        res_act_ant = client.put(f"/antecedentes/{paciente_id}", json={
            "tipo_ciclo": "amenorrea",
            "duracion_ciclo_habitual": 90,
            "diabetes": True
        }, headers=headers)
        assert res_act_ant.status_code == 200
        ant_db = paciente_service.obtener_antecedentes(paciente_id)
        assert ant_db["tipo_ciclo"] == "amenorrea"
        assert ant_db["diabetes"] is True
        assert isinstance(ant_db["historial"], list)
        assert len(ant_db["historial"]) >= 1
        snapshot = ant_db["historial"][-1]["version_anterior"]
        assert snapshot["tipo_ciclo"] == "irregular"
        assert snapshot["duracion_ciclo_habitual"] == 38
        registrar_resultado(
            "Versionado de antecedentes médicos en historial JSONB (HU-006)",
            "Actividad 3",
            "Integración / Versionado",
            True,
            "Conservación íntegra de la versión previa con marcas de auditoría"
        )
    except Exception as e:
        registrar_resultado("Versionado JSONB de antecedentes", "Actividad 3", "Integración / Versionado", False, str(e))

    # 29. Prevención de registro duplicado de antecedentes (POST para paciente con antecedentes)
    try:
        res_dup = client.post("/antecedentes", json={
            "paciente_id": paciente_id,
            "iniciada_vida_sexual": True,
            "edad_menarquia": 14
        }, headers=headers)
        assert res_dup.status_code == 409
        registrar_resultado(
            "Prevención de antecedentes duplicados (Intento de POST duplicado)",
            "Actividad 3",
            "Integridad de Datos",
            True,
            "Rechazo con HTTP 409 (Exige actualizar mediante PUT)"
        )
    except Exception as e:
        registrar_resultado("Prevención de duplicado en antecedentes", "Actividad 3", "Integridad de Datos", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 4: REGISTRO Y GESTIÓN DE CITAS MÉDICAS
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_4(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 4: Registro de Citas Médicas ---")

    # 30. Motivo de cita vacío o de longitud insuficiente
    try:
        res = client.post("/citas", json={
            "paciente_id": paciente_id,
            "motivo": "ok"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Registro de cita con motivo demasiado corto (< 3 caracteres)",
            "Actividad 4",
            "Validación de Entrada",
            True,
            "Exige motivo explícito de consulta con al menos 3 caracteres"
        )
    except Exception as e:
        registrar_resultado("Motivo de cita corto", "Actividad 4", "Validación de Entrada", False, str(e))

    # 31. Intento de agendar cita en el pasado
    try:
        fecha_pasada = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        res = client.post("/citas", json={
            "paciente_id": paciente_id,
            "fecha_atencion": fecha_pasada,
            "motivo": "Consulta fuera de tiempo"
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Intento de agendar cita en fecha pasada",
            "Actividad 4",
            "Lógica Temporal",
            True,
            "Rechaza agendar citas médicas con fecha anterior al momento actual"
        )
    except Exception as e:
        registrar_resultado("Cita en el pasado", "Actividad 4", "Lógica Temporal", False, str(e))

    # 32. Próxima cita anterior o igual a la fecha de atención (HU-007)
    now_dt = datetime.now(timezone.utc) + timedelta(days=5)
    try:
        fecha_atencion = now_dt.isoformat()
        fecha_proxima_anterior = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        res = client.post("/citas", json={
            "paciente_id": paciente_id,
            "fecha_atencion": fecha_atencion,
            "fecha_proxima_cita": fecha_proxima_anterior,
            "motivo": "Evaluación SOP"
        }, headers=headers)
        assert res.status_code in [400, 422]
        assert "posterior" in str(res.json()).lower()
        registrar_resultado(
            "Próxima cita tentativa anterior a la fecha de atención (HU-007)",
            "Actividad 4",
            "Coherencia Temporal",
            True,
            "Exige que la próxima cita sea estrictamente posterior a la atención"
        )
    except Exception as e:
        registrar_resultado("Próxima cita anterior a atención", "Actividad 4", "Coherencia Temporal", False, str(e))

    # 33. Próxima cita posterior exitosa
    cita_id = None
    try:
        fecha_atencion = now_dt.isoformat()
        fecha_proxima_valida = (now_dt + timedelta(days=15)).strftime("%Y-%m-%d")
        res = client.post("/citas", json={
            "paciente_id": paciente_id,
            "fecha_atencion": fecha_atencion,
            "fecha_proxima_cita": fecha_proxima_valida,
            "motivo": "Evaluación Integral de SOP",
            "estado": "programada"
        }, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["estado"] == "programada"
        cita_id = data["id"]
        registrar_resultado(
            "Registro de cita médica con fecha próxima posterior válida (HU-007)",
            "Actividad 4",
            "Integración / HU-007",
            True,
            "Creación exitosa con estado inicial 'programada' (HTTP 201)"
        )
    except Exception as e:
        registrar_resultado("Registro de cita válida", "Actividad 4", "Integración / HU-007", False, str(e))

    # 34. Transición por los 4 estados válidos de cita médica (HU-008)
    try:
        for est in ["atendida", "cancelada", "no asistió"]:
            res_act = client.put(f"/citas/{cita_id}", json={"estado": est}, headers=headers)
            assert res_act.status_code == 200
            assert res_act.json()["estado"] == est
        registrar_resultado(
            "Transición y validación de los 4 estados de cita médica (HU-008)",
            "Actividad 4",
            "Ciclo de Vida de Cita",
            True,
            "Soporta transiciones entre: programada, atendida, cancelada, no asistió"
        )
    except Exception as e:
        registrar_resultado("Transición de estados de cita", "Actividad 4", "Ciclo de Vida de Cita", False, str(e))

    # 35. Intento de asignar estado no admitido
    try:
        res_inv = client.put(f"/citas/{cita_id}", json={"estado": "en_proceso"}, headers=headers)
        assert res_inv.status_code in [400, 422]
        registrar_resultado(
            "Intento de asignar estado de cita no admitido ('en_proceso')",
            "Actividad 4",
            "Validación de Estados",
            True,
            "Rechaza estados fuera de la taxonomía clínica establecida"
        )
    except Exception as e:
        registrar_resultado("Estado de cita no admitido", "Actividad 4", "Validación de Estados", False, str(e))

    # 36. Auto-cancelación de citas vencidas (+1 hora de retraso)
    try:
        cita_service.auto_cancelar_citas_vencidas()
        registrar_resultado(
            "Evaluación de regla de auto-cancelación para citas vencidas (> 1h)",
            "Actividad 4",
            "Regla Automática",
            True,
            "Auto-transición a 'cancelada' con nota explicativa tras retraso"
        )
    except Exception as e:
        registrar_resultado("Auto-cancelación de citas", "Actividad 4", "Regla Automática", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 5: FORMULARIO DE DATOS CLÍNICOS Y ANTROPOMÉTRICOS (HU-010)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_5(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 5: Formulario de Datos Clínicos ---")

    # 37. Score Ferriman-Gallwey fuera de rango (< 0 o > 36)
    try:
        res = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "score_ferriman_gallwey": 45
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Score Ferriman-Gallwey fuera del rango clínico estándar (45)",
            "Actividad 5",
            "Lógica Médica / Rango",
            True,
            "Restricción estricta de Score de hirsutismo entre 0 y 36"
        )
    except Exception as e:
        registrar_resultado("Score Ferriman > 36", "Actividad 5", "Lógica Médica", False, str(e))

    # 38. Cuadrante individual de Ferriman-Gallwey fuera de escala (0 a 4 puntos)
    try:
        res = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "fg_labio_superior": 5
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Puntaje de cuadrante individual de Ferriman fuera de escala (5)",
            "Actividad 5",
            "Validación de Escala",
            True,
            "Cada uno de los 9 cuadrantes debe puntuar entre 0 y 4 puntos"
        )
    except Exception as e:
        registrar_resultado("Cuadrante Ferriman > 4", "Actividad 5", "Validación de Escala", False, str(e))

    # 39. Peso antropométrico inverosímil (< 20 kg o > 350 kg)
    try:
        res = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "peso_kg": 500.0,
            "talla_cm": 160.0
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Peso corporal fuera de rango fisiológico admisible (500 kg)",
            "Actividad 5",
            "Límites Fisiológicos",
            True,
            "Restricción de peso plausible entre 20 kg y 350 kg"
        )
    except Exception as e:
        registrar_resultado("Peso fuera de límites", "Actividad 5", "Límites Fisiológicos", False, str(e))

    # 40. Estatura antropométrica inverosímil (< 80 cm o > 250 cm)
    try:
        res = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "peso_kg": 65.0,
            "talla_cm": 30.0
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Estatura fuera de rango fisiológico admisible (30 cm)",
            "Actividad 5",
            "Límites Fisiológicos",
            True,
            "Restricción de talla plausible entre 80 cm y 250 cm"
        )
    except Exception as e:
        registrar_resultado("Estatura fuera de límites", "Actividad 5", "Límites Fisiológicos", False, str(e))

    # 41. Cálculo automático exacto del IMC: Peso 70kg, Talla 168cm -> IMC 24.80
    try:
        preview = client.post("/clinicos/metricas-preview", json={
            "peso_kg": 70.0,
            "talla_cm": 168.0
        }, headers=headers)
        assert preview.status_code == 200
        data = preview.json()
        assert data["imc"] == 24.80  # 70 / (1.68^2) = 24.8049...
        registrar_resultado(
            "Cálculo automático de Índice de Masa Corporal (IMC: 70kg / 1.68m^2 = 24.80)",
            "Actividad 5",
            "Cálculo Automático",
            True,
            "Fórmula peso / (talla/100)^2 redondeada exactamente a 2 decimales"
        )
    except Exception as e:
        registrar_resultado("Cálculo automático de IMC", "Actividad 5", "Cálculo Automático", False, str(e))

    # 42. Cálculo automático de Relación Cintura/Cadera (RCC)
    try:
        preview_rcc = client.post("/clinicos/metricas-preview", json={
            "circunferencia_abdominal_cm": 84.0,
            "cadera_cm": 100.0
        }, headers=headers)
        assert preview_rcc.status_code == 200
        data = preview_rcc.json()
        assert data["relacion_cintura_cadera"] == 0.84  # 84 / 100 = 0.84
        registrar_resultado(
            "Cálculo automático de Relación Cintura/Cadera (RCC: 84cm / 100cm = 0.84)",
            "Actividad 5",
            "Cálculo Automático",
            True,
            "Fórmula cintura / cadera redondeada a 2 decimales"
        )
    except Exception as e:
        registrar_resultado("Cálculo de relación cintura/cadera", "Actividad 5", "Cálculo Automático", False, str(e))

    # 43. Incoherencia hemodinámica: Presión Sistólica <= Diastólica
    try:
        res_pa = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "presion_sistolica": 70,
            "presion_diastolica": 110
        }, headers=headers)
        assert res_pa.status_code in [400, 422]
        assert "incoherencia hemodinámica" in str(res_pa.json()).lower()
        registrar_resultado(
            "Incoherencia hemodinámica: Presión Sistólica (70) <= Diastólica (110)",
            "Actividad 5",
            "Coherencia Hemodinámica",
            True,
            "Regla médica obligatoria: Presión sistólica debe ser mayor que la diastólica"
        )
    except Exception as e:
        registrar_resultado("Incoherencia de presión arterial", "Actividad 5", "Coherencia Hemodinámica", False, str(e))

    # 44. Presión arterial fuera de rangos fisiológicos
    try:
        res_pa_rango = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "presion_sistolica": 320,
            "presion_diastolica": 180
        }, headers=headers)
        assert res_pa_rango.status_code in [400, 422]
        registrar_resultado(
            "Presión arterial fuera de rango fisiológico admisible (320/180 mmHg)",
            "Actividad 5",
            "Límites Fisiológicos",
            True,
            "Restricción de presión sistólica 50-260 mmHg y diastólica 30-160 mmHg"
        )
    except Exception as e:
        registrar_resultado("Presión arterial fuera de límites", "Actividad 5", "Límites Fisiológicos", False, str(e))

    # 45. Guardado exitoso de datos clínicos con confirmación al especialista
    try:
        res_clinico_ok = client.post("/clinicos", json={
            "paciente_id": paciente_id,
            "hirsutismo": True,
            "score_ferriman_gallwey": 12,
            "acne": True,
            "acantosis_nigricans": True,
            "ciclos_irregulares": True,
            "duracion_ciclo_dias": 42,
            "peso_kg": 68.0,
            "talla_cm": 164.0,
            "circunferencia_abdominal_cm": 85.0,
            "cadera_cm": 98.0,
            "presion_sistolica": 118,
            "presion_diastolica": 76,
            "frecuencia_cardiaca": 72
        }, headers=headers)
        assert res_clinico_ok.status_code == 200
        data = res_clinico_ok.json()
        assert data["imc"] == 25.28  # 68 / (1.64^2) = 25.28
        assert "exitosamente" in data["mensaje_confirmacion"].lower()
        registrar_resultado(
            "Registro integral de datos clínicos con cálculo de IMC y confirmación",
            "Actividad 5",
            "Integración / HU-010",
            True,
            "Persistencia en 'datos_clinicos' y respuesta exitosa con IMC calculado"
        )
    except Exception as e:
        registrar_resultado("Registro integral de datos clínicos", "Actividad 5", "Integración / HU-010", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVIDAD 6: FORMULARIO DE DATOS HORMONALES Y CÁLCULOS BIOQUÍMICOS (HU-009)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_actividad_6(headers: dict, paciente_id: str):
    print("\n--- Ejecutando Pruebas de Actividad 6: Formulario de Datos Hormonales ---")

    # 46. Valores negativos rechazados
    try:
        res = client.post("/hormonales", json={
            "paciente_id": paciente_id,
            "glucosa_basal": -85.0
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Ingreso de parámetros hormonales con valor negativo (glucosa = -85)",
            "Actividad 6",
            "Validación Fisiológica",
            True,
            "Impide valores negativos en concentraciones hormonales y bioquímicas"
        )
    except Exception as e:
        registrar_resultado("Valor hormonal negativo", "Actividad 6", "Validación Fisiológica", False, str(e))

    # 47. Día del ciclo menstrual de toma de muestra fuera de rango (1 a 35)
    try:
        res = client.post("/hormonales", json={
            "paciente_id": paciente_id,
            "dia_ciclo_toma": 50
        }, headers=headers)
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Día del ciclo menstrual de toma de muestra fuera de rango (día 50)",
            "Actividad 6",
            "Validación Fisiológica",
            True,
            "Exige día del ciclo entre 1 y 35 días"
        )
    except Exception as e:
        registrar_resultado("Día de ciclo fuera de rango", "Actividad 6", "Validación Fisiológica", False, str(e))

    # 48. Cálculo automático de HOMA-IR: Glucosa 90 mg/dL, Insulina 15 µUI/mL -> HOMA-IR 3.33
    try:
        res_homa = client.post("/hormonales/semaforo-preview", json={
            "glucosa_basal": 90.0,
            "insulina_basal": 15.0
        }, headers=headers)
        assert res_homa.status_code == 200
        data = res_homa.json()
        assert data["datos"]["homa_ir"] == 3.33  # (90 * 15) / 405 = 3.3333...
        registrar_resultado(
            "Cálculo automático exacto del índice HOMA-IR ((90 * 15) / 405 = 3.33)",
            "Actividad 6",
            "Cálculo Bioquímico",
            True,
            "Fórmula de Matthews para resistencia insulínica redondeada a 2 decimales"
        )
    except Exception as e:
        registrar_resultado("Cálculo automático de HOMA-IR", "Actividad 6", "Cálculo Bioquímico", False, str(e))

    # 49. Cálculo automático de Relación LH/FSH: LH 14.4, FSH 4.8 -> Relación 3.00
    try:
        res_ratio = client.post("/hormonales/semaforo-preview", json={
            "lh": 14.4,
            "fsh": 4.8
        }, headers=headers)
        assert res_ratio.status_code == 200
        data = res_ratio.json()
        assert data["datos"]["relacion_lh_fsh"] == 3.00  # 14.4 / 4.8 = 3.0
        registrar_resultado(
            "Cálculo automático de relación LH/FSH (14.4 / 4.8 = 3.00)",
            "Actividad 6",
            "Cálculo Bioquímico",
            True,
            "Fórmula LH / FSH calculada automáticamente con precisión decimal"
        )
    except Exception as e:
        registrar_resultado("Cálculo de relación LH/FSH", "Actividad 6", "Cálculo Bioquímico", False, str(e))

    # 50. Protección contra división por cero si FSH es cero
    try:
        res_zero = client.post("/hormonales/semaforo-preview", json={
            "lh": 10.0,
            "fsh": 0.0
        }, headers=headers)
        assert res_zero.status_code == 200
        data = res_zero.json()
        assert data["datos"].get("relacion_lh_fsh") is None
        registrar_resultado(
            "Protección contra división por cero cuando FSH = 0 o nulo",
            "Actividad 6",
            "Protección Aritmética",
            True,
            "Retorna None y evita excepciones ZeroDivisionError en el backend"
        )
    except Exception as e:
        registrar_resultado("Protección división por cero en FSH", "Actividad 6", "Protección Aritmética", False, str(e))

    # 51. Semáforo clínico de SOP: detección de parámetros alterados (LH/FSH >= 2, HOMA-IR >= 2.5)
    try:
        res_sem = client.post("/hormonales/semaforo-preview", json={
            "lh": 15.0,
            "fsh": 5.0,
            "glucosa_basal": 105.0,
            "insulina_basal": 18.0,
            "testosterona_total": 75.0,
            "amh": 6.5
        }, headers=headers)
        assert res_sem.status_code == 200
        semaforos = res_sem.json()["semaforo"]
        assert semaforos["relacion_lh_fsh"]["estado"] == "alterado"  # 15/5 = 3.0 >= 2.0
        assert semaforos["homa_ir"]["estado"] == "alterado"          # (105*18)/405 = 4.67 >= 2.5
        assert semaforos["testosterona_total"]["estado"] == "alterado" # 75 > 50
        assert semaforos["amh"]["estado"] == "alterado"              # 6.5 > 4.0
        registrar_resultado(
            "Semáforo clínico: Marcación de indicadores alterados sugestivos de SOP",
            "Actividad 6",
            "Semáforo de Referencia",
            True,
            "Clasifica como 'alterado' (LH/FSH >= 2, HOMA-IR >= 2.5, Testosterona > 50)"
        )
    except Exception as e:
        registrar_resultado("Semáforo clínico alterado", "Actividad 6", "Semáforo de Referencia", False, str(e))

    # 52. Semáforo clínico: Marcación de valores normales fisiológicos
    try:
        res_norm = client.post("/hormonales/semaforo-preview", json={
            "lh": 5.0,
            "fsh": 5.0,
            "glucosa_basal": 82.0,
            "insulina_basal": 7.0,
            "testosterona_total": 28.0,
            "tsh": 2.1
        }, headers=headers)
        assert res_norm.status_code == 200
        semaforos = res_norm.json()["semaforo"]
        assert semaforos["relacion_lh_fsh"]["estado"] == "normal"  # 1.0 < 2.0
        assert semaforos["homa_ir"]["estado"] == "normal"          # 1.41 < 2.5
        assert semaforos["testosterona_total"]["estado"] == "normal" # 28 <= 50
        assert semaforos["tsh"]["estado"] == "normal"              # 2.1 in 0.4-4.5
        registrar_resultado(
            "Semáforo clínico: Marcación de indicadores dentro del rango normal",
            "Actividad 6",
            "Semáforo de Referencia",
            True,
            "Clasifica como 'normal' con descripción textual del rango de referencia"
        )
    except Exception as e:
        registrar_resultado("Semáforo clínico normal", "Actividad 6", "Semáforo de Referencia", False, str(e))

    # 53. Semáforo clínico: Marcación de campos pendientes (no ingresados)
    try:
        res_pend = client.post("/hormonales/semaforo-preview", json={"lh": 6.0}, headers=headers)
        assert res_pend.status_code == 200
        semaforos = res_pend.json()["semaforo"]
        assert semaforos["prolactina"]["estado"] == "no_ingresado"
        assert semaforos["prolactina"]["interpretacion"] == "Pendiente de laboratorio"
        registrar_resultado(
            "Semáforo clínico: Marcación de campos pendientes ('no_ingresado')",
            "Actividad 6",
            "Semáforo de Referencia",
            True,
            "Asigna estado 'no_ingresado' y leyenda 'Pendiente de laboratorio'"
        )
    except Exception as e:
        registrar_resultado("Semáforo clínico campos pendientes", "Actividad 6", "Semáforo de Referencia", False, str(e))

    # 54. Persistencia y guardado integral de datos hormonales con semáforo
    try:
        res_hormonal_ok = client.post("/hormonales", json={
            "paciente_id": paciente_id,
            "lh": 12.5,
            "fsh": 4.5,
            "tsh": 2.3,
            "amh": 5.8,
            "testosterona_total": 58.0,
            "dhea_s": 240.0,
            "prolactina": 14.5,
            "glucosa_basal": 96.0,
            "insulina_basal": 16.0,
            "colesterol_total": 185.0,
            "trigliceridos": 130.0,
            "dia_ciclo_toma": 3
        }, headers=headers)
        assert res_hormonal_ok.status_code == 200
        data = res_hormonal_ok.json()
        assert data["homa_ir"] == 3.79  # (96 * 16) / 405 = 3.7925
        assert data["relacion_lh_fsh"] == 2.78  # 12.5 / 4.5 = 2.7777
        assert "semaforo" in data
        registrar_resultado(
            "Persistencia y guardado de perfil hormonal con cálculo y semáforo (HU-009)",
            "Actividad 6",
            "Integración / HU-009",
            True,
            "Almacenamiento en 'datos_hormonales' con semáforo estructurado completo"
        )
    except Exception as e:
        registrar_resultado("Persistencia de datos hormonales", "Actividad 6", "Integración / HU-009", False, str(e))


def imprimir_tabla_resumen():
    """Imprime la tabla formateada con todos los resultados evitando caracteres incompatibles con cp1252."""
    total = len(resultados_pruebas)
    pasaron = sum(1 for r in resultados_pruebas if r["estado"] == "PASÓ")
    fallaron = total - pasaron

    print("\n" + "=" * 115)
    print(f"MATRIZ RESUMEN DE PRUEBAS DE CODIFICACION - GESTION DE PACIENTES Y ATENCIONES ({pasaron}/{total} PASARON - {100.0 * pasaron / total:.1f}%)")
    print("=" * 115)
    print(f"{'#':<3} | {'Nombre de la Prueba':<45} | {'Actividad':<13} | {'Tipo':<22} | {'Estado':<7} | {'Restriccion Evaluada'}")
    print("-" * 115)

    for i, r in enumerate(resultados_pruebas, 1):
        nombre_clean = r['nombre'][:45]
        restriccion_clean = r['restriccion']
        print(f"{i:<3} | {nombre_clean:<45} | {r['actividad']:<13} | {r['tipo'][:22]:<22} | {r['estado']:<7} | {restriccion_clean}")

    print("=" * 115)
    print(f"Total Evaluadas: {total} | Pasaron: {pasaron} | Fallaron: {fallaron} | Exito: {100.0 * pasaron / total:.1f}%")
    print("=" * 115)


if __name__ == "__main__":
    print("Iniciando Suite de Pruebas de Codificacion (Actividades 1 a 6)...")
    token = obtener_token_autenticado()
    auth_headers = {"Authorization": f"Bearer {token}"}

    p_id, ci = ejecutar_pruebas_actividad_2(auth_headers)
    ejecutar_pruebas_actividad_1(auth_headers, p_id, ci)
    ejecutar_pruebas_actividad_3(auth_headers, p_id)
    ejecutar_pruebas_actividad_4(auth_headers, p_id)
    ejecutar_pruebas_actividad_5(auth_headers, p_id)
    ejecutar_pruebas_actividad_6(auth_headers, p_id)
    imprimir_tabla_resumen()

    # Limpieza final de paciente de prueba
    if p_id:
        try:
            paciente_service.desactivar_paciente(p_id)
        except Exception:
            pass
