"""Baseline records and PostgreSQL spatial storage; adopts legacy installations."""
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not sa.inspect(connection).has_table("nwis_records"):
        op.create_table("nwis_records", sa.Column("kind", sa.String(40), primary_key=True),
                        sa.Column("id", sa.String(80), primary_key=True), sa.Column("payload", sa.Text(), nullable=False))
    if connection.dialect.name == "postgresql":
        script = (Path(__file__).resolve().parents[1]/"001_postgis.sql").read_text()
        for statement in script.split(";"):
            if statement.strip():
                op.execute(statement)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.drop_table("nwis_trajectories")
    op.drop_table("nwis_records")
