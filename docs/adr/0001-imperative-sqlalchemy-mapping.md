# Mapeo imperativo de SQLAlchemy

El proyecto usa `mapper_registry.map_imperatively()` en `app/db/orm.py` para mapear los domain models a las tablas, en lugar del enfoque declarativo de SQLAlchemy (clases que heredan de `Base` con `Column` como atributos). Los domain models son dataclasses puros en `app/model/domain/`, completamente desacoplados de SQLAlchemy.

Esto es deliberado: separa el modelo de dominio de la infraestructura de persistencia, permitiendo que los domain models evolucionen sin depender del ORM y facilitando tests unitarios sin base de datos. El costo es más boilerplate en el mapeo.

Revertirlo a declarativo implicaría acoplar los domain models a SQLAlchemy, perdiendo la separación de capas.
