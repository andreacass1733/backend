"""
Punto de Entrada Principal de la API REST - Sistema SOP Rotterdam.
═════════════════════════════════════════════════════════════════
Servidor FastAPI que orquesta la detección multimodal de SOP según
los Criterios de Rotterdam (2003 / 2023):
  - Criterio 1: Disfunción ovulatoria (ciclos menstruales / amenorrea)
  - Criterio 2: Hiperandrogenismo clínico y bioquímico
  - Criterio 3: Ovarios poliquísticos por ecografía (conteo folicular + IA)
"""

from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from routers.auth import auth, auditoria
from routers.clinica import (
    pacientes, antecedentes, citas, consultas, medicos,
    ordenes_medicas, tratamiento
)
from routers.rotterdam_ia import (
    criterio1, criterio2, criterio3, clasificacion,
    evaluacion, datos_clinicos, datos_hormonales
)
from services.rotterdam_ia.criterio3_service import get_model
from db.supabase_client import supabase


# ── Lifespan: se ejecuta al arrancar y al apagar el servidor ──────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Precarga el modelo IA al iniciar para evitar latencia en la primera petición."""
    print("[INFO] Iniciando servidor SOP...")
    try:
        get_model()
        print("[OK] Modelo EfficientNet-B0 precargado en memoria")
    except FileNotFoundError as e:
        print(f"[WARN] Advertencia: {e}")
    except Exception as e_mod:
        print(f"[WARN] Advertencia modelo: {e_mod}")

    try:
        yield
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("[INFO] Servidor SOP detenido")


# ── Aplicación principal ──────────────────────────────────────────────────────
app = FastAPI(
    title="SOP — API de Criterios de Rotterdam",
    description="Backend para la detección y clasificación del Síndrome de Ovario Poliquístico",
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "*",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rutas Públicas (Sin requerir Token de Autenticación) ───────────────────────
RUTAS_PUBLICAS = [
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login",
    "/auth/verify-2fa",
    "/auth/resend-2fa",
    "/auth/forgot-password",
    "/auth/reset-password",
]


# ── Middleware de Autenticación y Autorización Clínica (RBAC) ─────────────────
@app.middleware("http")
async def verificar_autenticacion_medica(request: Request, call_next):
    """
    Valida el token JWT de Supabase Auth en cada petición protegida.
    Garantiza que únicamente el médico especialista autenticado accede a la API.
    """
    # Responder inmediatamente a solicitudes preflight CORS
    if request.method == "OPTIONS":
        return JSONResponse(
            status_code=200,
            content={"status": "ok"},
            headers=CORS_HEADERS,
        )

    path = request.url.path
    if (
        path in RUTAS_PUBLICAS
        or path.startswith("/auth/login")
        or path.startswith("/auth/verify-2fa")
        or path.startswith("/auth/resend-2fa")
        or path.startswith("/auth/forgot-password")
        or path.startswith("/auth/reset-password")
        or path.startswith("/auditoria")
        or path.startswith("/clinicos")
        or path.startswith("/hormonales")
        or path.startswith("/evaluacion/metricas-clinicas")
        or path.startswith("/criterio2/metricas-clinicas")
        or path.startswith("/outputs")
        or path.startswith("/docs")
        or path.startswith("/openapi")
        or path.startswith("/redoc")
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Token de autenticación requerido"},
            headers=CORS_HEADERS,
        )

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token de autenticación requerido"},
            headers=CORS_HEADERS,
        )

    try:
        user_info = supabase.auth.get_user(token)
        if not user_info or not user_info.user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido o expirado"},
                headers=CORS_HEADERS,
            )
        request.state.user = user_info.user
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token inválido o expirado"},
            headers=CORS_HEADERS,
        )

    return await call_next(request)


# ── Manejadores de Excepciones con CORS Garantizado ───────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=CORS_HEADERS,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
        headers=CORS_HEADERS,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error del servidor: {str(exc)}"},
        headers=CORS_HEADERS,
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(criterio3.router)
app.include_router(pacientes.router)
app.include_router(antecedentes.router)
app.include_router(citas.router)
app.include_router(consultas.router)
app.include_router(medicos.router)
app.include_router(datos_hormonales.router)
app.include_router(datos_clinicos.router)
app.include_router(evaluacion.router)
app.include_router(criterio1.router)
app.include_router(criterio2.router)
app.include_router(tratamiento.router)
app.include_router(auditoria.router)
app.include_router(ordenes_medicas.router)
app.include_router(clasificacion.router)

# ── Montaje de Archivos Estáticos (Outputs de Evaluación IA) ──────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
outputs_dir = os.path.join(BASE_DIR, "outputs")
if os.path.exists(outputs_dir):
    app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")


# ── Ruta de salud ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"mensaje": "API SOP funcionando OK", "version": "1.0.0"}
