from typing import Any, List, Sequence, Tuple
from loguru import logger
from sqlalchemy.sql import Select
from sqlalchemy import Table
from sqlalchemy.sql.expression import select
import abc

class BaseRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, *args, **kwargs):
        raise NotImplementedError("Debe implementarse en las clases derivadas")

    @abc.abstractmethod
    def add(self, *args, **kwargs):
        raise NotImplementedError("Debe implementarse en las clases derivadas")
