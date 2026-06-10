#!/bin/sh
# Aplica las migraciones pendientes y luego arranca la API.
# Que las migraciones corran aquí (y no en el lifespan de FastAPI) garantiza
# que el esquema esté listo antes de aceptar peticiones, y que un fallo de
# migración detenga el arranque del contenedor de forma visible.
set -e

echo "[entrypoint] Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Migraciones OK. Arrancando uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8003}"
