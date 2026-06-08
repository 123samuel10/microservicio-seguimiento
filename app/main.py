from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.database import init_db
from app.controllers.practica_controller import router as practica_router

settings = get_settings()

DESCRIPTION = """
## Microservicio de Seguimiento de Prácticas

Registra y hace seguimiento del ciclo de vida de las prácticas profesionales en **Emplea Humboldt**.

### Ciclo de vida de una práctica
1. La empresa registra el inicio en `POST /api/v1/practicas/` (postulación aceptada).
2. El estudiante envía informes periódicos en `POST /api/v1/practicas/{id}/informes`.
3. La empresa evalúa al estudiante en `POST /api/v1/practicas/{id}/evaluaciones`.
4. La empresa finaliza la práctica en `POST /api/v1/practicas/{id}/finalizar`.

### Estados de una práctica
`EN_CURSO` → `FINALIZADA` / `SUSPENDIDA`

### Documentos soportados
- `contrato` — contrato de práctica firmado
- `arl` — afiliación a riesgos laborales
- `evaluacion_final` — evaluación final de la empresa
- `certificado` — certificado de finalización
"""

TAGS_METADATA = [
    {
        "name": "Seguimiento de Prácticas",
        "description": "Gestión completa de prácticas: registro, informes periódicos, evaluaciones, documentos y finalización.",
    },
    {
        "name": "Health",
        "description": "Verificación del estado del servicio.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(practica_router, prefix="/api/v1")


@app.get("/health", tags=["Health"], summary="Estado del servicio")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=TAGS_METADATA,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token JWT obtenido en el microservicio de autenticación.",
        }
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
