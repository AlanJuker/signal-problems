from alembic import context
from sqlalchemy import engine_from_config, pool

from signal_problems.infrastructure.database import Base
from signal_problems.infrastructure.settings import DATABASE_URL

config = context.config
url = config.get_main_option("sqlalchemy.url") or DATABASE_URL

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connectable = engine_from_config(
        {"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
