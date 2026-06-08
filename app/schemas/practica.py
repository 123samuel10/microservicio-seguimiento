from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from app.models.practica import (
    EstadoPractica,
    TipoDocumentoPractica,
    TipoEvaluador,
)


# --- Evaluación ---

class EvaluacionCreate(BaseModel):
    tipo_evaluador: TipoEvaluador
    calificacion: float = Field(ge=0.0, le=5.0)
    comentarios: Optional[str] = Field(None, max_length=2000)
    puntualidad: Optional[float] = Field(None, ge=0.0, le=5.0)
    calidad_trabajo: Optional[float] = Field(None, ge=0.0, le=5.0)
    trabajo_en_equipo: Optional[float] = Field(None, ge=0.0, le=5.0)
    iniciativa: Optional[float] = Field(None, ge=0.0, le=5.0)


class EvaluacionResponse(EvaluacionCreate):
    id: uuid.UUID
    practica_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Informe periódico ---

class InformeCreate(BaseModel):
    periodo_numero: int = Field(ge=1)
    descripcion_actividades: str = Field(min_length=20)
    logros: Optional[str] = None
    dificultades: Optional[str] = None


class InformeUpdate(BaseModel):
    descripcion_actividades: Optional[str] = Field(None, min_length=20)
    logros: Optional[str] = None
    dificultades: Optional[str] = None


class InformeResponse(BaseModel):
    id: uuid.UUID
    practica_id: uuid.UUID
    periodo_numero: int
    descripcion_actividades: str
    logros: Optional[str] = None
    dificultades: Optional[str] = None
    url_documento: Optional[str] = None
    aprobado_por_empresa: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Documento ---

class DocumentoPracticaResponse(BaseModel):
    id: uuid.UUID
    tipo: TipoDocumentoPractica
    url: str
    nombre_archivo: Optional[str] = None
    descripcion: Optional[str] = None
    uploaded_by: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentoUploadResponse(BaseModel):
    practica_id: uuid.UUID
    tipo: TipoDocumentoPractica
    url: str
    mensaje: str


# --- Práctica ---

class PracticaCreate(BaseModel):
    postulacion_id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    fecha_inicio: date
    fecha_fin_estimada: date
    programa_academico: Optional[str] = None
    universidad: Optional[str] = None
    observaciones: Optional[str] = None

    @field_validator("fecha_fin_estimada")
    @classmethod
    def fecha_fin_posterior(cls, v: date, info) -> date:
        inicio = info.data.get("fecha_inicio")
        if inicio and v <= inicio:
            raise ValueError("fecha_fin_estimada debe ser posterior a fecha_inicio")
        return v


class PracticaUpdate(BaseModel):
    observaciones: Optional[str] = None
    fecha_fin_estimada: Optional[date] = None
    programa_academico: Optional[str] = None
    universidad: Optional[str] = None


class PracticaResponse(BaseModel):
    id: uuid.UUID
    postulacion_id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    estado: EstadoPractica
    fecha_inicio: date
    fecha_fin_estimada: date
    fecha_fin_real: Optional[date] = None
    calificacion_final: Optional[float] = None
    programa_academico: Optional[str] = None
    universidad: Optional[str] = None
    observaciones: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    documentos: List[DocumentoPracticaResponse] = []
    evaluaciones: List[EvaluacionResponse] = []
    informes: List[InformeResponse] = []

    model_config = {"from_attributes": True}


class PracticaResumenResponse(BaseModel):
    id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    estado: EstadoPractica
    fecha_inicio: date
    fecha_fin_estimada: date
    fecha_fin_real: Optional[date] = None
    calificacion_final: Optional[float] = None

    model_config = {"from_attributes": True}


# --- Finalización ---

class FinalizarPracticaRequest(BaseModel):
    calificacion_final: float = Field(ge=0.0, le=5.0)
    observaciones: Optional[str] = None
    aprobada: bool = True


# --- Métricas ---

class MetricasPracticas(BaseModel):
    total: int
    activas: int
    finalizadas: int
    reprobadas: int
    suspendidas: int
    tasa_aprobacion: float
    calificacion_promedio: Optional[float]
    duracion_promedio_dias: Optional[float]
    por_empresa: dict
    por_programa: dict
