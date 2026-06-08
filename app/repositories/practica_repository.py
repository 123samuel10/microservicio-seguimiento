from __future__ import annotations

import uuid
from datetime import date
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.practica import (
    Practica,
    DocumentoPractica,
    EvaluacionDesempeno,
    InformePeriodico,
    EstadoPractica,
    TipoDocumentoPractica,
    TipoEvaluador,
)


class PracticaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, practica_id: uuid.UUID) -> Optional[Practica]:
        result = await self.db.execute(
            select(Practica)
            .options(
                selectinload(Practica.documentos),
                selectinload(Practica.evaluaciones),
                selectinload(Practica.informes),
            )
            .where(Practica.id == practica_id)
        )
        return result.scalar_one_or_none()

    async def get_by_postulacion(self, postulacion_id: uuid.UUID) -> Optional[Practica]:
        result = await self.db.execute(
            select(Practica).where(Practica.postulacion_id == postulacion_id)
        )
        return result.scalar_one_or_none()

    async def listar_por_estudiante(self, estudiante_id: uuid.UUID) -> List[Practica]:
        result = await self.db.execute(
            select(Practica)
            .options(selectinload(Practica.documentos), selectinload(Practica.evaluaciones), selectinload(Practica.informes))
            .where(Practica.estudiante_id == estudiante_id)
            .order_by(Practica.fecha_inicio.desc())
        )
        return list(result.scalars().all())

    async def listar_por_empresa(self, empresa_id: uuid.UUID) -> List[Practica]:
        result = await self.db.execute(
            select(Practica)
            .options(selectinload(Practica.documentos), selectinload(Practica.evaluaciones), selectinload(Practica.informes))
            .where(Practica.empresa_id == empresa_id)
            .order_by(Practica.fecha_inicio.desc())
        )
        return list(result.scalars().all())

    async def listar_activas(self) -> List[Practica]:
        result = await self.db.execute(
            select(Practica).where(Practica.estado == EstadoPractica.en_curso)
        )
        return list(result.scalars().all())

    async def crear(self, datos: dict) -> Practica:
        practica = Practica(**datos)
        self.db.add(practica)
        await self.db.flush()
        await self.db.refresh(practica)
        return practica

    async def actualizar(self, practica: Practica, datos: dict) -> Practica:
        for campo, valor in datos.items():
            if valor is not None:
                setattr(practica, campo, valor)
        await self.db.flush()
        await self.db.refresh(practica)
        return practica

    async def cambiar_estado(
        self,
        practica: Practica,
        nuevo_estado: EstadoPractica,
        fecha_fin_real: Optional[date] = None,
        calificacion_final: Optional[float] = None,
    ) -> Practica:
        practica.estado = nuevo_estado
        if fecha_fin_real:
            practica.fecha_fin_real = fecha_fin_real
        if calificacion_final is not None:
            practica.calificacion_final = calificacion_final
        await self.db.flush()
        await self.db.refresh(practica)
        return practica

    # --- Métricas ---

    async def contar_total(self) -> int:
        result = await self.db.execute(select(func.count(Practica.id)))
        return result.scalar_one()

    async def contar_por_estado(self) -> dict:
        result = await self.db.execute(
            select(Practica.estado, func.count(Practica.id)).group_by(Practica.estado)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def calificacion_promedio_global(self) -> Optional[float]:
        result = await self.db.execute(
            select(func.avg(Practica.calificacion_final)).where(
                Practica.calificacion_final.isnot(None)
            )
        )
        val = result.scalar_one_or_none()
        return round(float(val), 2) if val else None

    async def duracion_promedio_dias(self) -> Optional[float]:
        result = await self.db.execute(
            select(Practica.fecha_inicio, Practica.fecha_fin_real).where(
                Practica.fecha_fin_real.isnot(None)
            )
        )
        filas = result.all()
        if not filas:
            return None
        total = sum((f.fecha_fin_real - f.fecha_inicio).days for f in filas)
        return round(total / len(filas), 1)

    async def contar_por_empresa(self) -> dict:
        result = await self.db.execute(
            select(Practica.empresa_id, func.count(Practica.id))
            .group_by(Practica.empresa_id)
            .order_by(func.count(Practica.id).desc())
            .limit(20)
        )
        return {str(row[0]): row[1] for row in result.all()}

    async def contar_por_programa(self) -> dict:
        result = await self.db.execute(
            select(Practica.programa_academico, func.count(Practica.id))
            .where(Practica.programa_academico.isnot(None))
            .group_by(Practica.programa_academico)
            .order_by(func.count(Practica.id).desc())
        )
        return {row[0]: row[1] for row in result.all()}


class DocumentoPracticaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(
        self,
        practica_id: uuid.UUID,
        tipo: TipoDocumentoPractica,
        url: str,
        uploaded_by: str,
        nombre_archivo: Optional[str] = None,
        descripcion: Optional[str] = None,
    ) -> DocumentoPractica:
        doc = DocumentoPractica(
            practica_id=practica_id,
            tipo=tipo,
            url=url,
            uploaded_by=uploaded_by,
            nombre_archivo=nombre_archivo,
            descripcion=descripcion,
        )
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        return doc


class EvaluacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(self, practica_id: uuid.UUID, datos: dict) -> EvaluacionDesempeno:
        ev = EvaluacionDesempeno(practica_id=practica_id, **datos)
        self.db.add(ev)
        await self.db.flush()
        await self.db.refresh(ev)
        return ev

    async def promedio_por_practica(self, practica_id: uuid.UUID) -> Optional[float]:
        result = await self.db.execute(
            select(func.avg(EvaluacionDesempeno.calificacion)).where(
                EvaluacionDesempeno.practica_id == practica_id
            )
        )
        val = result.scalar_one_or_none()
        return round(float(val), 2) if val else None


class InformeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, informe_id: uuid.UUID) -> Optional[InformePeriodico]:
        result = await self.db.execute(
            select(InformePeriodico).where(InformePeriodico.id == informe_id)
        )
        return result.scalar_one_or_none()

    async def crear(self, practica_id: uuid.UUID, datos: dict) -> InformePeriodico:
        informe = InformePeriodico(practica_id=practica_id, **datos)
        self.db.add(informe)
        await self.db.flush()
        await self.db.refresh(informe)
        return informe

    async def actualizar(self, informe: InformePeriodico, datos: dict) -> InformePeriodico:
        for campo, valor in datos.items():
            if valor is not None:
                setattr(informe, campo, valor)
        await self.db.flush()
        await self.db.refresh(informe)
        return informe

    async def aprobar(self, informe: InformePeriodico) -> InformePeriodico:
        informe.aprobado_por_empresa = True
        await self.db.flush()
        await self.db.refresh(informe)
        return informe

    async def actualizar_url(self, informe: InformePeriodico, url: str) -> InformePeriodico:
        informe.url_documento = url
        await self.db.flush()
        await self.db.refresh(informe)
        return informe
