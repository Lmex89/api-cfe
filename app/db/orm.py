from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, func
from sqlalchemy.orm import registry

from model.domain.url_model import UrlModel

# Create a registry instance
mapper_registry = registry()


metadata = MetaData()
################################################################################
### Se debe de realizar el mapeo entre clases de negocio y la base de datos
### el mapeo se hace del modo "tradicional" de SQLAlquemy
################################################################################
urls_table = Table(
    "urls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("short_code", String(10), nullable=False, unique=True, index=True),
    Column("original_url", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("expires_at", DateTime, nullable=True),
    Column("visits", Integer, nullable=False, server_default="0"),
    Column("active", Integer, nullable=False, server_default="1"),
)


################################################################################
### Este método se llama al inicio del programa, no se debe de cambiar el
### nombre de la función y debe de contener todos los mapeos
################################################################################
def start_mappers():
    mapper_registry.map_imperatively(
        UrlModel,
        urls_table,
        properties={
            "id": urls_table.c.id,
            "short_code": urls_table.c.short_code,
            "original_url": urls_table.c.original_url,
            "created_at": urls_table.c.created_at,
            "expires_at": urls_table.c.expires_at,
            "visits": urls_table.c.visits,
            "active": urls_table.c.active
        },
    )
