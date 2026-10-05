"""Apply version-tracked Alembic migrations on the repository connection."""
from pathlib import Path
from alembic import command
from alembic.config import Config


def upgrade(engine):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1]/"migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from .config import get_settings
    upgrade(create_engine(get_settings().database_url))
