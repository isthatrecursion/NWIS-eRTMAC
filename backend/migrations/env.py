from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Run python -m app.migrate to supply the configured connection")
context.configure(connection=connection, target_metadata=None)
with context.begin_transaction():
    context.run_migrations()
