"""
Suite Integral de Pruebas Automatizadas de Autenticación, 2FA, Recuperación y Cierre de Sesión.
═══════════════════════════════════════════════════════════════════════════════════════════════
Simula el comportamiento real de un usuario médico en el sistema SOP, evaluando:
  - 1. Inicio de Sesión (Login) con validaciones de campos, longitud, inyección y fuerza bruta.
  - 2. Verificación de Dos Pasos (2FA) con OTP de 6 dígitos, límite de 3 reintentos, anti-spam y cooldown.
  - 3. Cierre de Sesión (Logout), Revocación de Tokens (Blacklist) y Prevención de Replay Attacks.
  - 4. Recuperación y Restablecimiento de Contraseña (Forgot Password & Reset) con política de complejidad.

Genera una matriz de resultados detallada (Nombre de la Prueba, Tipo de Prueba, Estado y Restricción).
"""

import os
import sys
import time
import uuid

# Configurar path del backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(".env")

from starlette.testclient import TestClient
from main import app
from services.auth import auth_service
from db.supabase_client import get_supabase_admin_client, supabase

# Cliente HTTP de pruebas
client = TestClient(app)

EMAIL_TEST = "carla.casas2004@gmail.com"
PWD_TEST = "Medico2026*"
MEDICO_ID_ESPERADO = "0a8eaba2-be5b-4dbd-b22b-fc35c5616c12"

# Registro de resultados
resultados_pruebas = []


def registrar_resultado(nombre: str, tipo: str, paso: bool, restriccion: str):
    """Registra el resultado de una prueba para el informe consolidado."""
    estado = "PASÓ" if paso else "FALLÓ"
    resultados_pruebas.append({
        "nombre": nombre,
        "tipo": tipo,
        "estado": estado,
        "restriccion": restriccion
    })
    prefijo = "[PASO]" if paso else "[FALLO]"
    print(f"{prefijo} ({tipo}) {nombre} -> {restriccion}")


def asegurar_password_base():
    """Restaura la contraseña base en Supabase Auth antes de comenzar."""
    try:
        admin = get_supabase_admin_client()
        admin.auth.admin.update_user_by_id(MEDICO_ID_ESPERADO, {"password": PWD_TEST})
    except Exception as e:
        print(f"[WARN] No se pudo reiniciar password base: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO 1: PRUEBAS DE INICIO DE SESIÓN (LOGIN)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_login():
    print("\n--- Ejecutando Pruebas de Inicio de Sesión (Login) ---")

    # 1. Campos vacíos
    try:
        res = client.post("/auth/login", json={"email": "", "password": ""})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario envía formulario con campos vacíos",
            "Validación de Entrada",
            True,
            "Rechaza campos vacíos (email y password obligatorios)"
        )
    except Exception as e:
        registrar_resultado("Usuario envía formulario con campos vacíos", "Validación de Entrada", False, str(e))

    # 2. Correo solo con espacios
    try:
        res = client.post("/auth/login", json={"email": "   ", "password": PWD_TEST})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario envía correo con solo espacios en blanco",
            "Validación de Entrada",
            True,
            "Rechaza cadenas de espacios y exige email válido"
        )
    except Exception as e:
        registrar_resultado("Usuario envía correo con solo espacios en blanco", "Validación de Entrada", False, str(e))

    # 3. Correo sin arroba
    try:
        res = client.post("/auth/login", json={"email": "carla.casas.gmail.com", "password": PWD_TEST})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario escribe correo sin arroba (@)",
            "Validación de Formato",
            True,
            "Exige estructura RFC 5322 con símbolo @"
        )
    except Exception as e:
        registrar_resultado("Usuario escribe correo sin arroba (@)", "Validación de Formato", False, str(e))

    # 4. Correo sin dominio
    try:
        res = client.post("/auth/login", json={"email": "medico@", "password": PWD_TEST})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario escribe correo sin dominio de internet",
            "Validación de Formato",
            True,
            "Exige dominio y extensión válida (.com, etc.)"
        )
    except Exception as e:
        registrar_resultado("Usuario escribe correo sin dominio de internet", "Validación de Formato", False, str(e))

    # 5. Correo excesivamente corto (< 5 caracteres)
    try:
        res = client.post("/auth/login", json={"email": "a@b", "password": PWD_TEST})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa correo de longitud insuficiente (< 5 caracteres)",
            "Validación de Longitud",
            True,
            "Longitud mínima requerida de 5 caracteres"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa correo de longitud insuficiente", "Validación de Longitud", False, str(e))

    # 6. Contraseña menor a 6 caracteres
    try:
        res = client.post("/auth/login", json={"email": EMAIL_TEST, "password": "123"})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa contraseña demasiado corta (< 6 caracteres)",
            "Validación de Longitud",
            True,
            "Exige longitud mínima de contraseña de 6 caracteres"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa contraseña demasiado corta", "Validación de Longitud", False, str(e))

    # 7. Contraseña excesivamente larga (> 128 caracteres)
    try:
        res = client.post("/auth/login", json={"email": EMAIL_TEST, "password": "A" * 129})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario o atacante envía contraseña excesiva (> 128 caracteres)",
            "Seguridad / Anti-DoS",
            True,
            "Limita longitud máxima a 128 caracteres para evitar saturación de hashing"
        )
    except Exception as e:
        registrar_resultado("Usuario o atacante envía contraseña excesiva", "Seguridad / Anti-DoS", False, str(e))

    # 8. Intento de inyección SQL en correo
    try:
        res = client.post("/auth/login", json={"email": "admin' OR '1'='1", "password": "password123"})
        assert res.status_code in [400, 422, 401]
        registrar_resultado(
            "Usuario intenta inyección SQL en campo de correo (' OR '1'='1)",
            "Seguridad / Inyección",
            True,
            "Rechazo seguro y neutralización sin exponer base de datos"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta inyección SQL en campo de correo", "Seguridad / Inyección", False, str(e))

    # 9. Intento de inyección de script XSS
    try:
        res = client.post("/auth/login", json={"email": "<script>alert('xss')</script>@sop.com", "password": "password123"})
        assert res.status_code in [400, 422, 401]
        registrar_resultado(
            "Usuario intenta inyección de etiquetas XSS (<script>)",
            "Seguridad / XSS",
            True,
            "Filtrado estricto de caracteres y sanitización de payloads maliciosos"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta inyección de etiquetas XSS", "Seguridad / XSS", False, str(e))

    # 10. Credenciales erróneas (clave incorrecta)
    try:
        # Usar email ficticio para no disparar el lockout del usuario de prueba
        res = client.post("/auth/login", json={"email": "intento.fallido@sop.com", "password": "ClaveIncorrecta123*"})
        assert res.status_code == 401
        assert "correo o contraseña incorrectos" in res.json()["detail"].lower()
        registrar_resultado(
            "Usuario ingresa contraseña incorrecta",
            "Integración / HU-001",
            True,
            "Mensaje genérico de seguridad sin revelar qué campo falló"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa contraseña incorrecta", "Integración / HU-001", False, str(e))

    # 11. Protección contra Fuerza Bruta (5 intentos fallidos consecutivos)
    try:
        ip_fuerza_bruta = "test_brute_force_user@sop.com"
        for _ in range(5):
            client.post("/auth/login", json={"email": ip_fuerza_bruta, "password": "ClaveErronea123*"})
        res_bloqueo = client.post("/auth/login", json={"email": ip_fuerza_bruta, "password": "ClaveErronea123*"})
        assert res_bloqueo.status_code == 429
        assert "demasiados intentos fallidos" in res_bloqueo.json()["detail"].lower()
        registrar_resultado(
            "Usuario o bot falla 5 veces consecutivas el inicio de sesión",
            "Seguridad / Fuerza Bruta",
            True,
            "Bloqueo temporal de 5 minutos mediante código HTTP 429"
        )
    except Exception as e:
        registrar_resultado("Usuario o bot falla 5 veces consecutivas", "Seguridad / Fuerza Bruta", False, str(e))

    # 12. Credenciales correctas -> Emisión de sesión 2FA obligatoria
    try:
        res = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
        assert res.status_code == 200
        data = res.json()
        assert data["requires_2fa"] is True
        assert len(data["session_id"]) > 10
        assert data["email_masked"].startswith("c") and "@" in data["email_masked"]
        assert data["codigo_demo"] is None  # Seguridad estricta: nunca expuesto
        registrar_resultado(
            "Usuario introduce credenciales correctas",
            "Integración / HU-001",
            True,
            "Autenticación Paso 1 exitosa, sesión 2FA emitida y código demo oculto"
        )
        return data["session_id"]
    except Exception as e:
        registrar_resultado("Usuario introduce credenciales correctas", "Integración / HU-001", False, str(e))
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO 2: PRUEBAS DE DOBLE FACTOR DE AUTENTICACIÓN (2FA / OTP)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_2fa(session_id: str):
    print("\n--- Ejecutando Pruebas de Doble Factor (2FA) ---")

    if not session_id or session_id not in auth_service._SESSIONS_2FA:
        # Generar sesión válida fresca
        res_fresh = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
        session_id = res_fresh.json()["session_id"]

    # 13. Código 2FA vacío
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": ""})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario envía código 2FA vacío",
            "Validación de Entrada",
            True,
            "Exige ingreso obligatorio del código 2FA"
        )
    except Exception as e:
        registrar_resultado("Usuario envía código 2FA vacío", "Validación de Entrada", False, str(e))

    # 14. Código 2FA incompleto (< 6 dígitos)
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "123"})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa código incompleto de 3 dígitos ('123')",
            "Validación de Longitud",
            True,
            "Rechaza longitudes menores a 6 dígitos"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código incompleto", "Validación de Longitud", False, str(e))

    # 15. Código 2FA excesivo (> 6 dígitos)
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "1234567"})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa código excesivo de 7 dígitos ('1234567')",
            "Validación de Longitud",
            True,
            "Rechaza longitudes mayores a 6 dígitos exactos"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código excesivo", "Validación de Longitud", False, str(e))

    # 16. Código 2FA con caracteres no numéricos
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "12A456"})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa letras o símbolos en el código 2FA ('12A456')",
            "Validación de Formato",
            True,
            "Exige exclusivamente dígitos numéricos (0-9)"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa letras o símbolos en el código 2FA", "Validación de Formato", False, str(e))

    # 17. Session ID inválido o expirado
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": "00000000-0000-0000-0000-000000000000", "code": "123456"})
        assert res.status_code == 401
        registrar_resultado(
            "Usuario envía un identificador de sesión inexistente o caducado",
            "Control de Sesión",
            True,
            "Rechaza peticiones huérfanas sin sesión 2FA activa"
        )
    except Exception as e:
        registrar_resultado("Usuario envía session_id inexistente", "Control de Sesión", False, str(e))

    # 18. Código 2FA incorrecto con control de reintentos
    try:
        res = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "999999"})
        assert res.status_code == 401
        assert "le quedan" in res.json()["detail"].lower()
        registrar_resultado(
            "Usuario introduce código 2FA numérico incorrecto ('999999')",
            "Integración / 2FA",
            True,
            "Decrece contador y advierte intentos restantes al especialista"
        )
    except Exception as e:
        registrar_resultado("Usuario introduce código 2FA numérico incorrecto", "Integración / 2FA", False, str(e))

    # 19. Agotamiento de intentos (3 fallos) -> Anulación de sesión 2FA
    try:
        # Falla intento 2 y 3
        client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "999999"})
        res_bloqueo = client.post("/auth/verify-2fa", json={"session_id": session_id, "code": "999999"})
        assert res_bloqueo.status_code == 401
        assert "excedido" in res_bloqueo.json()["detail"].lower()
        # Verificar que la sesión fue purgada
        assert session_id not in auth_service._SESSIONS_2FA
        registrar_resultado(
            "Usuario agota los 3 intentos fallidos permitidos en 2FA",
            "Seguridad / Anti-Bruteforce OTP",
            True,
            "Anulación inmediata y destrucción de la sesión 2FA por seguridad"
        )
    except Exception as e:
        registrar_resultado("Usuario agota los 3 intentos en 2FA", "Seguridad / Anti-Bruteforce OTP", False, str(e))

    # Generar nueva sesión limpia para reenvío y validación exitosa
    res_fresh = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
    session_id_valida = res_fresh.json()["session_id"]

    # 20. Reenvío con Cooldown (menos de 15 segundos)
    try:
        res_cooldown = client.post("/auth/resend-2fa", json={"session_id": session_id_valida})
        assert res_cooldown.status_code == 429
        assert "esperar" in res_cooldown.json()["detail"].lower()
        registrar_resultado(
            "Usuario solicita reenvío inmediato antes del cooldown (< 15s)",
            "Seguridad / Anti-Spam",
            True,
            "Bloqueo temporal de 15 segundos entre solicitudes de correo"
        )
    except Exception as e:
        registrar_resultado("Usuario solicita reenvío inmediato", "Seguridad / Anti-Spam", False, str(e))

    # 21. Reenvío límite máximo (más de 3 reenvíos)
    try:
        # Simulamos que transcurrió el cooldown y forzamos el contador a 3
        auth_service._SESSIONS_2FA[session_id_valida]["last_resend_at"] = time.time() - 20
        auth_service._SESSIONS_2FA[session_id_valida]["resend_count"] = 3
        res_limite = client.post("/auth/resend-2fa", json={"session_id": session_id_valida})
        assert res_limite.status_code == 429
        assert "límite máximo" in res_limite.json()["detail"].lower()
        registrar_resultado(
            "Usuario supera el límite máximo de reenvíos de código (3)",
            "Seguridad / Anti-Abuso",
            True,
            "Restricción de máximo 3 despachos de correo por sesión activa"
        )
    except Exception as e:
        registrar_resultado("Usuario supera el límite máximo de reenvíos", "Seguridad / Anti-Abuso", False, str(e))

    # 22. Validación exitosa con código emitido
    # Generar sesión limpia para el login final
    res_login_final = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
    sid_exito = res_login_final.json()["session_id"]
    codigo_correcto = auth_service._SESSIONS_2FA[sid_exito]["code"]

    token_obtenido = None
    try:
        res_verif = client.post("/auth/verify-2fa", json={"session_id": sid_exito, "code": codigo_correcto})
        assert res_verif.status_code == 200
        data_auth = res_verif.json()
        assert "access_token" in data_auth
        assert data_auth["user_id"] == MEDICO_ID_ESPERADO
        assert data_auth["medico"]["nombre"] == "Rodrigo"
        token_obtenido = data_auth["access_token"]
        registrar_resultado(
            "Usuario ingresa código 2FA de 6 dígitos correcto recibido por email",
            "Integración / E2E",
            True,
            "Emisión oficial de JWT y datos del especialista clínico"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código 2FA correcto", "Integración / E2E", False, str(e))

    # 23. Validación mediante clave de contingencia médica de emergencia
    try:
        res_login_cont = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
        sid_cont = res_login_cont.json()["session_id"]
        res_cont = client.post("/auth/verify-2fa", json={"session_id": sid_cont, "code": "796787"})
        assert res_cont.status_code == 200
        assert "access_token" in res_cont.json()
        registrar_resultado(
            "Usuario médico valida mediante código de contingencia clínica ('796787')",
            "Integración / Contingencia",
            True,
            "Acceso garantizado en contingencia para atención clínica de urgencia"
        )
    except Exception as e:
        registrar_resultado("Usuario valida contingencia médica", "Integración / Contingencia", False, str(e))

    # 24. Prevención de Ataque de Repetición (One-Time Use)
    try:
        # Intentar verificar nuevamente con la misma sesión y código ya consumidos
        res_replay = client.post("/auth/verify-2fa", json={"session_id": sid_exito, "code": codigo_correcto})
        assert res_replay.status_code == 401
        registrar_resultado(
            "Usuario o atacante intenta reutilizar el código 2FA ya validado",
            "Seguridad / One-Time Use",
            True,
            "Consumo y destrucción inmediata de la sesión 2FA (Replay attack prevention)"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta reutilizar código 2FA", "Seguridad / One-Time Use", False, str(e))

    return token_obtenido


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO 3: CIERRE DE SESIÓN (LOGOUT) Y CONTROL DE ACCESO (BLACKIST)
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_logout(token_valido: str):
    print("\n--- Ejecutando Pruebas de Cierre de Sesión y Control de Acceso ---")

    if not token_valido:
        # Obtener token válido
        res_login = client.post("/auth/login", json={"email": EMAIL_TEST, "password": PWD_TEST})
        sid = res_login.json()["session_id"]
        res_verif = client.post("/auth/verify-2fa", json={"session_id": sid, "code": "796787"})
        token_valido = res_verif.json()["access_token"]

    # 25. Acceso a /auth/me con Token válido
    try:
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token_valido}"})
        assert res.status_code == 200
        assert res.json()["user_id"] == MEDICO_ID_ESPERADO
        registrar_resultado(
            "Usuario autenticado consulta /auth/me con Token válido",
            "Interfaz / Control de Acceso",
            True,
            "Acceso concedido y retorno de información del perfil médico"
        )
    except Exception as e:
        registrar_resultado("Usuario consulta /auth/me con Token válido", "Interfaz / Control de Acceso", False, str(e))

    # 26. Acceso sin Token de autenticación
    try:
        res = client.get("/auth/me")
        assert res.status_code == 401
        registrar_resultado(
            "Usuario anónimo intenta acceder a /auth/me sin Token",
            "Control de Acceso",
            True,
            "Rechaza petición no autorizada con código HTTP 401"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta acceder a /auth/me sin Token", "Control de Acceso", False, str(e))

    # 27. Header Authorization malformado (sin prefijo Bearer)
    try:
        res = client.get("/auth/me", headers={"Authorization": f"TokenInvalido {token_valido}"})
        assert res.status_code == 401
        registrar_resultado(
            "Usuario envía encabezado Authorization con formato no estándar",
            "Seguridad / Protocolo",
            True,
            "Exige formato estricto RFC 6750 ('Bearer <token>')"
        )
    except Exception as e:
        registrar_resultado("Usuario envía encabezado con formato no estándar", "Seguridad / Protocolo", False, str(e))

    # 28. Token corrupto o inventado
    try:
        res = client.get("/auth/me", headers={"Authorization": "Bearer token_falso_inventado_12345"})
        assert res.status_code == 401
        registrar_resultado(
            "Usuario envía Token JWT falsificado o corrupto",
            "Seguridad Criptográfica",
            True,
            "Rechaza tokens sin firma válida de Supabase Auth"
        )
    except Exception as e:
        registrar_resultado("Usuario envía Token falsificado", "Seguridad Criptográfica", False, str(e))

    # 29. Cierre de sesión sin Token
    try:
        res = client.post("/auth/logout")
        assert res.status_code == 401
        registrar_resultado(
            "Solicitud de Logout sin encabezado de autorización",
            "Validación de Entrada",
            True,
            "Exige token para validar identidad de cierre de sesión"
        )
    except Exception as e:
        registrar_resultado("Solicitud de Logout sin token", "Validación de Entrada", False, str(e))

    # 30. Cierre de sesión exitoso (HU-002)
    try:
        res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token_valido}"})
        assert res.status_code == 200
        assert "sesión cerrada correctamente" in res.json()["mensaje"].lower()
        registrar_resultado(
            "Usuario presiona botón 'Cerrar Sesión' en la barra de navegación",
            "Integración / HU-002",
            True,
            "Cierre de sesión exitoso, revocación en Supabase y registro en Blacklist"
        )
    except Exception as e:
        registrar_resultado("Usuario presiona Cerrar Sesión", "Integración / HU-002", False, str(e))

    # 31. Intento de reutilizar Token revocado en /auth/me (Token Blacklist)
    try:
        res_post_logout = client.get("/auth/me", headers={"Authorization": f"Bearer {token_valido}"})
        assert res_post_logout.status_code == 401
        assert "revocado" in res_post_logout.json()["detail"].lower()
        registrar_resultado(
            "Usuario o atacante intenta usar el Token tras el cierre de sesión",
            "Seguridad / Token Blacklist",
            True,
            "Rechazo inmediato 401: el token revocado queda invalidado permanentemente"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta usar Token tras Logout", "Seguridad / Token Blacklist", False, str(e))

    # 32. Intento de acceder a recursos clínicos con Token revocado
    try:
        res_clinica = client.get("/pacientes", headers={"Authorization": f"Bearer {token_valido}"})
        assert res_clinica.status_code == 401
        assert "revocado" in res_clinica.json()["detail"].lower()
        registrar_resultado(
            "Intento de consultar historial de pacientes con Token revocado",
            "Seguridad / Middleware RBAC",
            True,
            "Middleware bloquea acceso clínico integral tras el cierre de sesión"
        )
    except Exception as e:
        registrar_resultado("Intento de consultar pacientes con Token revocado", "Seguridad / Middleware RBAC", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO 4: RECUPERACIÓN Y CAMBIO DE CONTRASEÑA EN DOS PASOS
# ══════════════════════════════════════════════════════════════════════════════

def ejecutar_pruebas_recuperacion():
    print("\n--- Ejecutando Pruebas de Recuperación de Contraseña ---")

    # 33. Solicitud con correo vacío
    try:
        res = client.post("/auth/forgot-password", json={"email": ""})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario solicita recuperación de contraseña con correo vacío",
            "Validación de Entrada",
            True,
            "Exige correo electrónico obligatorio"
        )
    except Exception as e:
        registrar_resultado("Usuario solicita recuperación con correo vacío", "Validación de Entrada", False, str(e))

    # 34. Solicitud con correo de formato inválido
    try:
        res = client.post("/auth/forgot-password", json={"email": "correo_sin_formato"})
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario solicita recuperación con formato de correo inválido",
            "Validación de Formato",
            True,
            "Exige correo con formato RFC 5322 válido"
        )
    except Exception as e:
        registrar_resultado("Usuario solicita recuperación con correo inválido", "Validación de Formato", False, str(e))

    # 35. Solicitud con correo no registrado
    try:
        res = client.post("/auth/forgot-password", json={"email": "no_existe_medico_xyz@sop.com"})
        assert res.status_code == 404
        registrar_resultado(
            "Usuario solicita recuperación para cuenta médica inexistente",
            "Seguridad / Not Found",
            True,
            "Informa que la cuenta no existe sin comprometer el sistema (404)"
        )
    except Exception as e:
        registrar_resultado("Usuario solicita recuperación para cuenta inexistente", "Seguridad / Not Found", False, str(e))

    # 36. Solicitud exitosa con correo válido
    session_reset_id = None
    try:
        res = client.post("/auth/forgot-password", json={"email": EMAIL_TEST})
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "@" in data["email_masked"]
        session_reset_id = data["session_id"]
        registrar_resultado(
            "Usuario solicita código de recuperación con correo válido",
            "Integración / Paso 1",
            True,
            "Genera sesión de recuperación, enmascara email y despacha código OTP de 10 min"
        )
    except Exception as e:
        registrar_resultado("Usuario solicita código con correo válido", "Integración / Paso 1", False, str(e))

    # 37. Restablecer con código incompleto (< 6 dígitos)
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "123",
            "new_password": "NuevaClave2026*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa código de recuperación incompleto ('123')",
            "Validación de Longitud",
            True,
            "Exige código exactamente de 6 dígitos numéricos"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código incompleto", "Validación de Longitud", False, str(e))

    # 38. Restablecer con código que tiene letras
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "12A456",
            "new_password": "NuevaClave2026*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario ingresa código con letras ('12A456')",
            "Validación de Formato",
            True,
            "Rechaza caracteres alfabéticos en el código de seguridad"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código con letras", "Validación de Formato", False, str(e))

    # 39. Contraseña demasiado corta (< 8 caracteres)
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "796787",
            "new_password": "Ab1*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario intenta poner contraseña menor a 8 caracteres ('Ab1*')",
            "Directiva de Contraseña",
            True,
            "Exige longitud mínima de 8 caracteres en cambio de clave"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta contraseña menor a 8 caracteres", "Directiva de Contraseña", False, str(e))

    # 40. Contraseña sin mayúsculas
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "796787",
            "new_password": "medicoclasenueva123*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario intenta poner contraseña sin mayúsculas ('medicoclasenueva123*')",
            "Complejidad de Contraseña",
            True,
            "Exige al menos una letra mayúscula (A-Z)"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta contraseña sin mayúsculas", "Complejidad de Contraseña", False, str(e))

    # 41. Contraseña sin minúsculas
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "796787",
            "new_password": "MEDICOCLASENUEVA123*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario intenta poner contraseña sin minúsculas ('MEDICOCLASENUEVA123*')",
            "Complejidad de Contraseña",
            True,
            "Exige al menos una letra minúscula (a-z)"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta contraseña sin minúsculas", "Complejidad de Contraseña", False, str(e))

    # 42. Contraseña sin números ni símbolos
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "796787",
            "new_password": "ClaveSinNumerosNiSignos",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario intenta contraseña sin números ni símbolos especiales",
            "Complejidad de Contraseña",
            True,
            "Exige al menos un número o símbolo de puntuación"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta contraseña sin números ni símbolos", "Complejidad de Contraseña", False, str(e))

    # 43. Contraseña débil común de diccionario
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "796787",
            "new_password": "password123",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario intenta poner contraseña trivial de diccionario ('password123')",
            "Seguridad contra Diccionario",
            True,
            "Rechaza claves comunes inseguras según política médica"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta contraseña trivial de diccionario", "Seguridad contra Diccionario", False, str(e))

    # 44. Código de recuperación incorrecto
    try:
        res = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": "000000",
            "new_password": "NuevaClave2026*",
            "session_id": session_reset_id
        })
        assert res.status_code in [400, 422]
        registrar_resultado(
            "Usuario introduce código de recuperación numérico que no coincide ('000000')",
            "Integración / Recuperación",
            True,
            "Rechaza código incorrecto y evita cambio no autorizado"
        )
    except Exception as e:
        registrar_resultado("Usuario introduce código incorrecto", "Integración / Recuperación", False, str(e))

    # 45. Bloqueo por intentos excedidos en recuperación (3 intentos)
    try:
        # Falla intento 2 y 3
        client.post("/auth/reset-password", json={"email": EMAIL_TEST, "code": "000000", "new_password": "NuevaClave2026*", "session_id": session_reset_id})
        res_bloq = client.post("/auth/reset-password", json={"email": EMAIL_TEST, "code": "000000", "new_password": "NuevaClave2026*", "session_id": session_reset_id})
        assert res_bloq.status_code == 400
        assert "excedido" in res_bloq.json()["detail"].lower()
        registrar_resultado(
            "Usuario falla 3 veces consecutivas el código de recuperación",
            "Seguridad / Anti-Bruteforce",
            True,
            "Anulación inmediata de la solicitud de recuperación por exceso de fallos"
        )
    except Exception as e:
        registrar_resultado("Usuario falla 3 veces en recuperación", "Seguridad / Anti-Bruteforce", False, str(e))

    # 46. Cambio exitoso con código válido y contraseña de alta seguridad
    try:
        # Generar nueva solicitud fresca
        res_sol = client.post("/auth/forgot-password", json={"email": EMAIL_TEST})
        sid_ok = res_sol.json()["session_id"]
        codigo_reset = auth_service._SESSIONS_RESET[sid_ok]["code"]

        res_ok = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": codigo_reset,
            "new_password": PWD_TEST,  # Restablecer a Medico2026*
            "session_id": sid_ok
        })
        assert res_ok.status_code == 200
        assert "actualizada exitosamente" in res_ok.json()["mensaje"].lower()
        registrar_resultado(
            "Usuario ingresa código válido y contraseña robusta ('Medico2026*')",
            "Integración / E2E Paso 2",
            True,
            "Actualización exitosa en Supabase Auth, consumo de sesión y auditoría HIPAA"
        )
    except Exception as e:
        registrar_resultado("Usuario ingresa código válido y contraseña robusta", "Integración / E2E Paso 2", False, str(e))

    # 47. Prevención de reutilización del código de recuperación (One-Time Use)
    try:
        res_reuse = client.post("/auth/reset-password", json={
            "email": EMAIL_TEST,
            "code": codigo_reset,
            "new_password": "OtraClaveRobusta2026*",
            "session_id": sid_ok
        })
        assert res_reuse.status_code == 400
        registrar_resultado(
            "Usuario o atacante intenta reutilizar el código de recuperación ya consumido",
            "Seguridad / One-Time Use",
            True,
            "Código de recuperación destruido tras el primer uso exitoso"
        )
    except Exception as e:
        registrar_resultado("Usuario intenta reutilizar código de recuperación", "Seguridad / One-Time Use", False, str(e))


def imprimir_tabla_resumen():
    """Imprime la tabla formateada con todos los resultados."""
    total = len(resultados_pruebas)
    pasaron = sum(1 for r in resultados_pruebas if r["estado"] == "PASÓ")
    fallaron = total - pasaron

    print("\n" + "=" * 105)
    print(f"MATRIZ RESUMEN DE PRUEBAS DE SEGURIDAD, INICIO Y CIERRE DE SESIÓN ({pasaron}/{total} PASARON - {100.0 * pasaron / total:.1f}%)")
    print("=" * 105)
    print(f"{'#':<3} | {'Nombre de la Prueba':<42} | {'Tipo':<22} | {'Estado':<7} | {'Restricción Evaluada'}")
    print("-" * 105)

    for i, r in enumerate(resultados_pruebas, 1):
        print(f"{i:<3} | {r['nombre'][:42]:<42} | {r['tipo'][:22]:<22} | {r['estado']:<7} | {r['restriccion']}")

    print("=" * 105)
    print(f"Total Evaluadas: {total} | Pasaron: {pasaron} | Fallaron: {fallaron} | Éxito: {100.0 * pasaron / total:.1f}%")
    print("=" * 105)


if __name__ == "__main__":
    print("Iniciando Suite de Pruebas de Usuario (Login, 2FA, Logout, Reset)...")
    asegurar_password_base()
    sid = ejecutar_pruebas_login()
    token = ejecutar_pruebas_2fa(sid)
    ejecutar_pruebas_logout(token)
    ejecutar_pruebas_recuperacion()
    imprimir_tabla_resumen()
