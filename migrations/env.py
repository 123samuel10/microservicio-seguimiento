"""Entorno de ejecución de Alembic (modo async con asyncpg).

La URL y los modelos se toman de la propia aplicación, de modo que las
migraciones siempre apuntan a la misma BD y al mismo esquema que usa el
servicio en runtime.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

from alembic import context

from app.config import get_settings
from app.database import Base

# Importar los modelos registra todas las tablas en Base.metadata.
# Necesario para que --autogenerate detecte cambios de esquema.
import app.models.practica  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inyectar la URL async desde la configuración de la app.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse a la BD (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def ensure_database_exists() -> None:
    """Crea la base de datos si no existe."""
    settings = get_settings()
    db_url = settings.DATABASE_URL

    # Extraer nombre de la BD del URL
    # Formato: postgresql+asyncpg://user:pass@host:port/dbname
    db_name = db_url.split("/")[-1].split("?")[0]

    # Conectarse a la BD 'postgres' (siempre existe) para crear nuestra BD
    admin_url = db_url.rsplit("/", 1)[0] + "/postgres"

    try:
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            # Verificar si la BD existe
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.scalar()

            if not exists:
                # Crear la BD
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"✓ Base de datos '{db_name}' creada exitosamente")
            else:
                print(f"○ Base de datos '{db_name}' ya existe")

        await admin_engine.dispose()
    except Exception as e:
        print(f"⚠ Error al verificar/crear la base de datos: {e}")
        # Continuar de todos modos - puede que ya exista


async def run_migrations_online() -> None:
    """Ejecuta las migraciones contra la BD usando el engine async."""
    # Asegurar que la base de datos existe antes de migrar
    await ensure_database_exists()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
