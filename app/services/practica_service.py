from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.practica import EstadoPractica, TipoDocumentoPractica
from app.repositories.practica_repository import (
    DocumentoPracticaRepository,
    EvaluacionRepository,
    InformeRepository,
    PracticaRepository,
)
from app.schemas.practica import (
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

settings = get_settings()


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def _subir_archivo_s3(file: UploadFile, key: str) -> str:
    s3 = _s3_client()
    try:
        contenido = await file.read()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=contenido,
            ContentType=file.content_type or "application/octet-stream",
        )
        return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al subir el archivo: {str(e)}",
        )


async def _verificar_vacante_publicada(vacante_id: uuid.UUID, token: str) -> None:
    url = f"{settings.EMPLEOS_SERVICE_URL}/api/v1/vacantes/{vacante_id}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo conectar con el servicio de empleos",
            )
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacante no encontrada")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Error al verificar la vacante")
    vacante = resp.json()
    if vacante.get("estado") not in {"publicada", "cubierta"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La práctica debe corresponder a una vacante publicada o cubierta",
        )


class PracticaService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PracticaRepository(db)
        self.doc_repo = DocumentoPracticaRepository(db)
        self.eval_repo = EvaluacionRepository(db)
        self.informe_repo = InformeRepository(db)

    async def crear_practica(self, datos: PracticaCreate, token: str) -> PracticaResponse:
        # Verificar vacante en microservicio de empleos
        await _verificar_vacante_publicada(datos.vacante_id, token)

        # Evitar prácticas duplicadas por postulación
        existente = await self.repo.get_by_postulacion(datos.postulacion_id)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una práctica para esta postulación",
            )

        practica = await self.repo.crear(datos.model_dump())
        practica = await self.repo.get_by_id(practica.id)
        return PracticaResponse.model_validate(practica)

    async def get_practica(self, practica_id: uuid.UUID, usuario_id: uuid.UUID) -> PracticaResponse:
        practica = await self._get_y_validar_acceso(practica_id, usuario_id)
        return PracticaResponse.model_validate(practica)

    async def actualizar_practica(
        self, practica_id: uuid.UUID, empresa_id: uuid.UUID, datos: PracticaUpdate
    ) -> PracticaResponse:
        practica = await self._get_de_empresa(practica_id, empresa_id)
        if practica.estado != EstadoPractica.en_curso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede editar una práctica en curso",
            )
        await self.repo.actualizar(practica, datos.model_dump(exclude_none=True))
        practica = await self.repo.get_by_id(practica_id)
        return PracticaResponse.model_validate(practica)

    async def finalizar_practica(
        self, practica_id: uuid.UUID, empresa_id: uuid.UUID, datos: FinalizarPracticaRequest
    ) -> PracticaResponse:
        practica = await self._get_de_empresa(practica_id, empresa_id)
        if practica.estado != EstadoPractica.en_curso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede finalizar una práctica en curso",
            )
        nuevo_estado = EstadoPractica.finalizada if datos.aprobada else EstadoPractica.reprobada
        await self.repo.cambiar_estado(
            practica,
            nuevo_estado,
            fecha_fin_real=date.today(),
            calificacion_final=datos.calificacion_final,
        )
        if datos.observaciones:
            await self.repo.actualizar(practica, {"observaciones": datos.observaciones})
        practica = await self.repo.get_by_id(practica_id)
        return PracticaResponse.model_validate(practica)

    async def suspender_practica(
        self, practica_id: uuid.UUID, empresa_id: uuid.UUID
    ) -> PracticaResponse:
        practica = await self._get_de_empresa(practica_id, empresa_id)
        if practica.estado != EstadoPractica.en_curso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede suspender una práctica en curso",
            )
        await self.repo.cambiar_estado(practica, EstadoPractica.suspendida)
        practica = await self.repo.get_by_id(practica_id)
        return PracticaResponse.model_validate(practica)

    async def mis_practicas(self, estudiante_id: uuid.UUID) -> List[PracticaResumenResponse]:
        practicas = await self.repo.listar_por_estudiante(estudiante_id)
        return [PracticaResumenResponse.model_validate(p) for p in practicas]

    async def practicas_empresa(self, empresa_id: uuid.UUID) -> List[PracticaResumenResponse]:
        practicas = await self.repo.listar_por_empresa(empresa_id)
        return [PracticaResumenResponse.model_validate(p) for p in practicas]

    # --- Evaluaciones ---

    async def agregar_evaluacion(
        self, practica_id: uuid.UUID, empresa_id: uuid.UUID, datos: EvaluacionCreate
    ) -> EvaluacionResponse:
        practica = await self._get_de_empresa(practica_id, empresa_id)
        if practica.estado not in {EstadoPractica.en_curso, EstadoPractica.finalizada}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede evaluar una práctica suspendida o reprobada",
            )
        ev = await self.eval_repo.crear(practica_id, datos.model_dump())

        # Recalcular calificación final como promedio
        promedio = await self.eval_repo.promedio_por_practica(practica_id)
        if promedio is not None:
            await self.repo.actualizar(practica, {"calificacion_final": promedio})

        return EvaluacionResponse.model_validate(ev)

    # --- Informes periódicos ---

    async def crear_informe(
        self, practica_id: uuid.UUID, estudiante_id: uuid.UUID, datos: InformeCreate
    ) -> InformeResponse:
        practica = await self._get_de_estudiante(practica_id, estudiante_id)
        if practica.estado != EstadoPractica.en_curso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden crear informes en prácticas en curso",
            )
        informe = await self.informe_repo.crear(practica_id, datos.model_dump())
        return InformeResponse.model_validate(informe)

    async def actualizar_informe(
        self, practica_id: uuid.UUID, informe_id: uuid.UUID, estudiante_id: uuid.UUID, datos: InformeUpdate
    ) -> InformeResponse:
        await self._get_de_estudiante(practica_id, estudiante_id)
        informe = await self._get_informe(informe_id, practica_id)
        if informe.aprobado_por_empresa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar un informe ya aprobado",
            )
        await self.informe_repo.actualizar(informe, datos.model_dump(exclude_none=True))
        return InformeResponse.model_validate(informe)

    async def aprobar_informe(
        self, practica_id: uuid.UUID, informe_id: uuid.UUID, empresa_id: uuid.UUID
    ) -> InformeResponse:
        await self._get_de_empresa(practica_id, empresa_id)
        informe = await self._get_informe(informe_id, practica_id)
        await self.informe_repo.aprobar(informe)
        return InformeResponse.model_validate(informe)

    # --- Documentos ---

    async def subir_documento(
        self,
        practica_id: uuid.UUID,
        usuario_id: uuid.UUID,
        tipo: TipoDocumentoPractica,
        file: UploadFile,
        uploaded_by: str,
        descripcion: Optional[str] = None,
    ) -> str:
        practica = await self.repo.get_by_id(practica_id)
        if not practica:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Práctica no encontrada")
        if practica.estudiante_id != usuario_id and practica.empresa_id != usuario_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta práctica")

        key = f"practicas/{practica_id}/{tipo.value}/{file.filename}"
        url = await _subir_archivo_s3(file, key)
        await self.doc_repo.crear(practica_id, tipo, url, uploaded_by, file.filename, descripcion)
        return url

    async def subir_documento_informe(
        self, practica_id: uuid.UUID, informe_id: uuid.UUID, estudiante_id: uuid.UUID, file: UploadFile
    ) -> InformeResponse:
        await self._get_de_estudiante(practica_id, estudiante_id)
        informe = await self._get_informe(informe_id, practica_id)
        key = f"practicas/{practica_id}/informes/{informe_id}/{file.filename}"
        url = await _subir_archivo_s3(file, key)
        await self.informe_repo.actualizar_url(informe, url)
        return InformeResponse.model_validate(informe)

    # --- Métricas ---

    async def get_metricas(self) -> MetricasPracticas:
        total = await self.repo.contar_total()
        por_estado = await self.repo.contar_por_estado()
        cal_promedio = await self.repo.calificacion_promedio_global()
        dur_promedio = await self.repo.duracion_promedio_dias()
        por_empresa = await self.repo.contar_por_empresa()
        por_programa = await self.repo.contar_por_programa()

        finalizadas = por_estado.get("finalizada", 0)
        reprobadas = por_estado.get("reprobada", 0)
        concluidas = finalizadas + reprobadas
        tasa_aprobacion = round(finalizadas / concluidas, 4) if concluidas else 0.0

        return MetricasPracticas(
            total=total,
            activas=por_estado.get("en_curso", 0),
            finalizadas=finalizadas,
            reprobadas=reprobadas,
            suspendidas=por_estado.get("suspendida", 0),
            tasa_aprobacion=tasa_aprobacion,
            calificacion_promedio=cal_promedio,
            duracion_promedio_dias=dur_promedio,
            por_empresa=por_empresa,
            por_programa=por_programa,
        )

    # --- helpers ---

    async def _get_y_validar_acceso(self, practica_id: uuid.UUID, usuario_id: uuid.UUID):
        practica = await self.repo.get_by_id(practica_id)
        if not practica:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Práctica no encontrada")
        if practica.estudiante_id != usuario_id and practica.empresa_id != usuario_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta práctica")
        return practica

    async def _get_de_empresa(self, practica_id: uuid.UUID, empresa_id: uuid.UUID):
        practica = await self.repo.get_by_id(practica_id)
        if not practica:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Práctica no encontrada")
        if practica.empresa_id != empresa_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta práctica")
        return practica

    async def _get_de_estudiante(self, practica_id: uuid.UUID, estudiante_id: uuid.UUID):
        practica = await self.repo.get_by_id(practica_id)
        if not practica:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Práctica no encontrada")
        if practica.estudiante_id != estudiante_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta práctica")
        return practica

    async def _get_informe(self, informe_id: uuid.UUID, practica_id: uuid.UUID):
        informe = await self.informe_repo.get_by_id(informe_id)
        if not informe or informe.practica_id != practica_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Informe no encontrado")
        return informe
