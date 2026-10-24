import re
from pydantic import BaseModel, field_validator
from typing import Optional
from schemas.clinica.medico_schema import MedicoResponse

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El correo electrónico es requerido")
        if len(clean) < 5 or len(clean) > 120:
            raise ValueError("El correo debe tener entre 5 y 120 caracteres")
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Formato de correo electrónico inválido")
        return clean.lower()

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La contraseña es requerida")
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        if len(v) > 128:
            raise ValueError("La contraseña excede la longitud máxima permitida (128 caracteres)")
        return v


class Verify2FARequest(BaseModel):
    session_id: str
    code: str

    @field_validator("session_id")
    @classmethod
    def validar_session_id(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El identificador de sesión es requerido")
        if len(clean) < 10:
            raise ValueError("Identificador de sesión 2FA inválido")
        return clean

    @field_validator("code")
    @classmethod
    def validar_code(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El código de verificación es requerido")
        if not clean.isdigit():
            raise ValueError("El código de verificación debe contener únicamente dígitos numéricos")
        if len(clean) != 6:
            raise ValueError("El código de verificación debe contener exactamente 6 dígitos")
        return clean


class Resend2FARequest(BaseModel):
    session_id: str

    @field_validator("session_id")
    @classmethod
    def validar_session_id(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El identificador de sesión es requerido")
        return clean


class InitialLoginResponse(BaseModel):
    requires_2fa: bool = True
    session_id: str
    email_masked: str
    telefono_masked: str
    codigo_demo: Optional[str] = None
    mensaje: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    medico: MedicoResponse


class LogoutResponse(BaseModel):
    mensaje: str


class UserSessionResponse(BaseModel):
    user_id: str
    email: str
    medico: MedicoResponse


# ── Recuperación y Cambio de Contraseña (Seguridad en 2 Pasos) ─────────────
class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El correo electrónico es requerido")
        if len(clean) < 5 or len(clean) > 120:
            raise ValueError("El correo debe tener entre 5 y 120 caracteres")
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Formato de correo electrónico inválido")
        return clean.lower()


class ForgotPasswordResponse(BaseModel):
    session_id: str
    email_masked: str
    mensaje: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str  # Código de 6 dígitos verificado por correo (obligatorio)
    new_password: str
    session_id: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El correo electrónico es requerido")
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Formato de correo electrónico inválido")
        return clean.lower()

    @field_validator("code")
    @classmethod
    def validar_code(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("El código de verificación es requerido")
        if not clean.isdigit():
            raise ValueError("El código de verificación debe contener únicamente dígitos numéricos")
        if len(clean) != 6:
            raise ValueError("El código de verificación debe contener exactamente 6 dígitos")
        return clean

    @field_validator("new_password")
    @classmethod
    def validar_new_password(cls, v: str) -> str:
        clean = (v or "").strip()
        if len(clean) < 8:
            raise ValueError("La nueva contraseña debe tener al menos 8 caracteres")
        if len(clean) > 128:
            raise ValueError("La contraseña excede la longitud máxima permitida (128 caracteres)")
        if not re.search(r"[A-Z]", clean):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r"[a-z]", clean):
            raise ValueError("La contraseña debe contener al menos una letra minúscula")
        if not re.search(r"[0-9\W_]", clean):
            raise ValueError("La contraseña debe contener al menos un número o símbolo especial")
        return clean


class ResetPasswordResponse(BaseModel):
    mensaje: str
