from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common.config import HOST, PORT, USER, PWD, DB
from db.orm import metadata

SQLALCHEMY_DATABASE_URL = f"mysql+mysqldb://{USER}:{PWD}@{HOST}:{PORT}/{DB}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    isolation_level="REPEATABLE READ",
    pool_pre_ping=True,
)

DEFAULT_SESSION_FACTORY = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    metadata.create_all(engine)
