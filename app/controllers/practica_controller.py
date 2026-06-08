from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.deps import UsuarioToken, get_current_user, require_empresa, require_estudiante
from app.database import get_db
from app.models.practica import TipoDocumentoPractica
from app.schemas.practica import (
    DocumentoUploadResponse,
    EvaluacionCreate,
    EvaluacionResponse,
    FinalizarPracticaRequest,
    InformeCreate,
    InformeResponse,
    InformeUpdate,
    MetricasPracticas,
    PracticaCreate,
    PracticaResponse,
    PracticaResumenResponse,
    PracticaUpdate,
)
from app.services.practica_service import PracticaService

router = APIRouter(prefix="/practicas", tags=["Seguimiento de Prácticas"])


# ── Práctica ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=PracticaResponse, status_code=status.HTTP_201_CREATED)
async def crear_practica(
    datos: PracticaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    """La empresa registra el inicio de una práctica (postulación aceptada)."""
    service = PracticaService(db)
    return await service.crear_practica(datos, usuario.raw_token)


@router.get("/mis-practicas", response_model=List[PracticaResumenResponse])
async def mis_practicas(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PracticaService(db)
    return await service.mis_practicas(usuario.id)


@router.get("/empresa/todas", response_model=List[PracticaResumenResponse])
async def practicas_empresa(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.practicas_empresa(usuario.id)


@router.get("/metricas", response_model=MetricasPracticas)
async def metricas(
    db: AsyncSession = Depends(get_db),
    _: UsuarioToken = Depends(get_current_user),
):
    service = PracticaService(db)
    return await service.get_metricas()


@router.get("/{practica_id}", response_model=PracticaResponse)
async def get_practica(
    practica_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = PracticaService(db)
    return await service.get_practica(uuid.UUID(practica_id), usuario.id)


@router.put("/{practica_id}", response_model=PracticaResponse)
async def actualizar_practica(
    practica_id: str,
    datos: PracticaUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.actualizar_practica(uuid.UUID(practica_id), usuario.id, datos)


@router.post("/{practica_id}/finalizar", response_model=PracticaResponse)
async def finalizar_practica(
    practica_id: str,
    datos: FinalizarPracticaRequest,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.finalizar_practica(uuid.UUID(practica_id), usuario.id, datos)


@router.post("/{practica_id}/suspender", response_model=PracticaResponse)
async def suspender_practica(
    practica_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.suspender_practica(uuid.UUID(practica_id), usuario.id)


# ── Evaluaciones ──────────────────────────────────────────────────────────────

@router.post("/{practica_id}/evaluaciones", response_model=EvaluacionResponse, status_code=status.HTTP_201_CREATED)
async def agregar_evaluacion(
    practica_id: str,
    datos: EvaluacionCreate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.agregar_evaluacion(uuid.UUID(practica_id), usuario.id, datos)


# ── Informes periódicos ───────────────────────────────────────────────────────

@router.post("/{practica_id}/informes", response_model=InformeResponse, status_code=status.HTTP_201_CREATED)
async def crear_informe(
    practica_id: str,
    datos: InformeCreate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PracticaService(db)
    return await service.crear_informe(uuid.UUID(practica_id), usuario.id, datos)


@router.put("/{practica_id}/informes/{informe_id}", response_model=InformeResponse)
async def actualizar_informe(
    practica_id: str,
    informe_id: str,
    datos: InformeUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PracticaService(db)
    return await service.actualizar_informe(
        uuid.UUID(practica_id), uuid.UUID(informe_id), usuario.id, datos
    )


@router.post("/{practica_id}/informes/{informe_id}/aprobar", response_model=InformeResponse)
async def aprobar_informe(
    practica_id: str,
    informe_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PracticaService(db)
    return await service.aprobar_informe(
        uuid.UUID(practica_id), uuid.UUID(informe_id), usuario.id
    )


@router.post("/{practica_id}/informes/{informe_id}/documento", response_model=InformeResponse)
async def subir_documento_informe(
    practica_id: str,
    informe_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PracticaService(db)
    return await service.subir_documento_informe(
        uuid.UUID(practica_id), uuid.UUID(informe_id), usuario.id, file
    )


# ── Documentos generales ──────────────────────────────────────────────────────

@router.post("/{practica_id}/documentos/{tipo}", response_model=DocumentoUploadResponse)
async def subir_documento(
    practica_id: str,
    tipo: TipoDocumentoPractica,
    descripcion: Optional[str] = Query(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = PracticaService(db)
    uploaded_by = usuario.tipo
    url = await service.subir_documento(
        uuid.UUID(practica_id), usuario.id, tipo, file, uploaded_by, descripcion
    )
    return DocumentoUploadResponse(
        practica_id=uuid.UUID(practica_id),
        tipo=tipo,
        url=url,
        mensaje="Documento subido correctamente",
    )
