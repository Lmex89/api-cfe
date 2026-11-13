"""Adapters for the Costo total TariffCatalog seam: UoW (production) and in-memory (tests)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class UowTariffCatalog:
    def __init__(self, uow) -> None:
        self.uow = uow

    def vivienda(self, vivienda_id):
        return self.uow.household_repository.get(vivienda_id)

    def periodo(self, periodo_id):
        return self.uow.billing_period_repository.get(periodo_id)

    def asignaciones(self, vivienda_id):
        hts = self.uow.household_tariff_repository.list(household_id=vivienda_id, limit=1000)
        return list(reversed(hts))

    def tarifa(self, tariff_id):
        return self.uow.tariff_repository.get(tariff_id)

    def version(self, tariff_id, year, month):
        return self.uow.tariff_version_repository.get_by_tariff_and_period_or_latest_before(
            tariff_id, year, month
        )

    def rangos(self, version_id):
        return self.uow.tariff_range_repository.list(tariff_version_id=version_id)


class CachedTariffCatalog:
    """Memoizes a catalog for one operation, so repeated pricing reads each datum once."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self._cache: Dict[Any, Any] = {}

    def _get(self, name, *args):
        key = (name, *args)
        if key not in self._cache:
            self._cache[key] = getattr(self._inner, name)(*args)
        return self._cache[key]

    def vivienda(self, *a): return self._get("vivienda", *a)
    def periodo(self, *a): return self._get("periodo", *a)
    def asignaciones(self, *a): return self._get("asignaciones", *a)
    def tarifa(self, *a): return self._get("tarifa", *a)
    def version(self, *a): return self._get("version", *a)
    def rangos(self, *a): return self._get("rangos", *a)


class InMemoryTariffCatalog:
    """Plain-list catalog; `asignaciones` are given oldest first, like the repository."""

    def __init__(self) -> None:
        self.viviendas: Dict[int, Any] = {}
        self.periodos: Dict[int, Any] = {}
        self.tarifas: Dict[int, Any] = {}
        self._asignaciones: List[Any] = []
        self._versiones: List[Any] = []
        self._rangos: List[Any] = []

    def add_asignacion(self, a): self._asignaciones.append(a)
    def add_version(self, v): self._versiones.append(v)
    def add_rango(self, r): self._rangos.append(r)

    def vivienda(self, vivienda_id): return self.viviendas.get(vivienda_id)
    def periodo(self, periodo_id): return self.periodos.get(periodo_id)
    def tarifa(self, tariff_id): return self.tarifas.get(tariff_id)

    def asignaciones(self, vivienda_id):
        return [a for a in reversed(self._asignaciones) if a.household_id == vivienda_id]

    def version(self, tariff_id, year, month) -> Optional[Any]:
        earlier = [
            v for v in self._versiones
            if v.tariff_id == tariff_id and (v.year, v.month) <= (year, month)
        ]
        return max(earlier, key=lambda v: (v.year, v.month), default=None)

    def rangos(self, version_id):
        return [r for r in self._rangos if r.tariff_version_id == version_id]
