from __future__ import annotations

import uuid
import enum
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, DateTime, Date, Enum, Text, Numeric, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class EstadoPractica(str, enum.Enum):
    en_curso = "en_curso"
    suspendida = "suspendida"
    finalizada = "finalizada"
    reprobada = "reprobada"


class TipoDocumentoPractica(str, enum.Enum):
    contrato_aprendizaje = "contrato_aprendizaje"
    aval_universitario = "aval_universitario"
    plan_trabajo = "plan_trabajo"
    informe_periodico = "informe_periodico"
    evaluacion_desempeno = "evaluacion_desempeno"
    certificado_finalizacion = "certificado_finalizacion"


class TipoEvaluador(str, enum.Enum):
    empresa = "empresa"
    universidad = "universidad"


class Practica(Base):
    __tablename__ = "practicas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # IDs denormalizados desde otros microservicios
    postulacion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    vacante_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    estudiante_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Datos de la práctica
    estado: Mapped[EstadoPractica] = mapped_column(
        Enum(EstadoPractica, name="estado_practica_enum"),
        default=EstadoPractica.en_curso,
        nullable=False,
        index=True,
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_estimada: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin_real: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Calificación final consolidada (promedio de evaluaciones)
    calificacion_final: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)

    # Metadatos del programa académico (snapshot del perfil estudiantil)
    programa_academico: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    universidad: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    documentos: Mapped[List[DocumentoPractica]] = relationship(
        back_populates="practica", cascade="all, delete-orphan"
    )
    evaluaciones: Mapped[List[EvaluacionDesempeno]] = relationship(
        back_populates="practica", cascade="all, delete-orphan",
        order_by="EvaluacionDesempeno.created_at",
    )
    informes: Mapped[List[InformePeriodico]] = relationship(
        back_populates="practica", cascade="all, delete-orphan",
        order_by="InformePeriodico.periodo_numero",
    )


class DocumentoPractica(Base):
    __tablename__ = "documentos_practica"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    practica_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practicas.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoDocumentoPractica] = mapped_column(
        Enum(TipoDocumentoPractica, name="tipo_doc_practica_enum"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(50), nullable=False)  # "estudiante"|"empresa"|"universidad"
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    practica: Mapped[Practica] = relationship(back_populates="documentos")


class EvaluacionDesempeno(Base):
    __tablename__ = "evaluaciones_desempeno"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    practica_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practicas.id", ondelete="CASCADE"), nullable=False
    )
    tipo_evaluador: Mapped[TipoEvaluador] = mapped_column(
        Enum(TipoEvaluador, name="tipo_evaluador_enum"), nullable=False
    )
    calificacion: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)  # 0.0 – 5.0
    comentarios: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Campos de rúbrica detallada
    puntualidad: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)
    calidad_trabajo: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)
    trabajo_en_equipo: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)
    iniciativa: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    practica: Mapped[Practica] = relationship(back_populates="evaluaciones")


class InformePeriodico(Base):
    __tablename__ = "informes_periodicos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    practica_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practicas.id", ondelete="CASCADE"), nullable=False
    )
    periodo_numero: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3…
    descripcion_actividades: Mapped[str] = mapped_column(Text, nullable=False)
    logros: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dificultades: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url_documento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aprobado_por_empresa: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    practica: Mapped[Practica] = relationship(back_populates="informes")
