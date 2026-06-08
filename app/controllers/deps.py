from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()


@dataclass
class UsuarioToken:
    id: uuid.UUID
    tipo: str
    raw_token: str


def _decode(token: str) -> UsuarioToken:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub: Optional[str] = payload.get("sub")
    tipo: Optional[str] = payload.get("tipo")
    if not sub or not tipo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token malformado")
    return UsuarioToken(id=uuid.UUID(sub), tipo=tipo, raw_token=token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UsuarioToken:
    return _decode(credentials.credentials)


def require_estudiante(usuario: UsuarioToken = Depends(get_current_user)) -> UsuarioToken:
    if usuario.tipo != "estudiante":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo estudiantes")
    return usuario


def require_empresa(usuario: UsuarioToken = Depends(get_current_user)) -> UsuarioToken:
    if usuario.tipo != "empresa":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo empresas")
    return usuario


def require_admin(usuario: UsuarioToken = Depends(get_current_user)) -> UsuarioToken:
    if usuario.tipo != "administrador_institucional":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores")
    return usuario
