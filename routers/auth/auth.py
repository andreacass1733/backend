"""
Router de Autenticación y Control de Acceso — Supabase Auth (JWT) + Doble Factor (2FA).
Endpoints correspondientes a la Iteración 1:
  - POST /auth/login       → HU-001 Paso 1: Validación de credenciales + emisión de 2FA
  - POST /auth/verify-2fa  → HU-001 Paso 2: Verificación de código 2FA y emisión de JWT
  - POST /auth/resend-2fa  → Reenvío de código de verificación 2FA con cooldown y límite
  - POST /auth/logout      → HU-002: Cierre de sesión, revocación en Blacklist e invalidación de JWT
  - GET  /auth/me          → Verificación de sesión activa y datos del especialista
"""

from fastapi import APIRouter, Header, Request, HTTPException
from typing import Optional

from schemas.auth.auth_schema import (
    LoginRequest,
    InitialLoginResponse,
    Verify2FARequest,
    Resend2FARequest,
    LoginResponse,
    LogoutResponse,
    UserSessionResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=InitialLoginResponse)
def login_endpoint(body: LoginRequest, request: Request):
    """
    HU-001: Valida correo y contraseña contra Supabase Auth con restricciones avanzadas.
    Obligatoriamente despacha código de Doble Factor (2FA) al correo electrónico.
    """
    client_ip = request.client.host if request.client else None
    return auth_service.iniciar_sesion(
        email=body.email,
        password=body.password,
        client_ip=client_ip,
    )


@router.post("/verify-2fa", response_model=LoginResponse)
def verify_2fa_endpoint(body: Verify2FARequest, request: Request):
    """
    HU-001 Paso 2: Verifica el código 2FA emitido (6 dígitos numéricos exactos).
    Si es válido, emite el token JWT de Supabase Auth y los datos del médico especialista.
    Aplica límite de 3 intentos fallidos y uso único (One-Time Use).
    """
    client_ip = request.client.host if request.client else None
    return auth_service.verificar_2fa(
        session_id=body.session_id,
        code=body.code,
        client_ip=client_ip
    )


@router.post("/resend-2fa")
def resend_2fa_endpoint(body: Resend2FARequest):
    """
    Genera un nuevo código 2FA con cooldown mínimo de 15s y máximo 3 intentos.
    """
    return auth_service.reenviar_2fa(session_id=body.session_id)


@router.post("/logout", response_model=LogoutResponse)
def logout_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    HU-002: Cierre de sesión del sistema.
    Invalida el token JWT en Supabase Auth, lo registra en la Blacklist de revocación y audita el cierre de sesión.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticación requerido o formato de header inválido")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token de autenticación requerido")

    client_ip = request.client.host if request.client else None
    return auth_service.cerrar_sesion(token=token, client_ip=client_ip)


@router.get("/me", response_model=UserSessionResponse)
def get_current_user_endpoint(authorization: Optional[str] = Header(None)):
    """
    Verifica si el token JWT actual es válido y devuelve los datos del médico especialista.
    Rechaza tokens revocados tras Logout o expirados.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticación requerido o formato de header inválido")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token de autenticación requerido")

    user = auth_service.verificar_token(token)
    medico_data = auth_service._obtener_datos_medico(user.id)

    return {
        "user_id": user.id,
        "email": user.email,
        "medico": medico_data,
    }


# ── Recuperación y Cambio de Contraseña ─────────────────────────────────────

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password_endpoint(body: ForgotPasswordRequest, request: Request):
    """
    Solicita la emisión de un código de recuperación de contraseña enviado al correo.
    """
    client_ip = request.client.host if request.client else None
    return auth_service.solicitar_recuperacion_contrasena(
        email=body.email,
        client_ip=client_ip
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password_endpoint(body: ResetPasswordRequest, request: Request):
    """
    Restablece y cambia la contraseña del especialista en Supabase Auth aplicando
    política de robustez de al menos 8 caracteres, mayúsculas, minúsculas y números/símbolos.
    """
    client_ip = request.client.host if request.client else None
    return auth_service.restablecer_contrasena(
        email=body.email,
        new_password=body.new_password,
        code=body.code,
        session_id=body.session_id,
        client_ip=client_ip
    )
