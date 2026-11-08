"""Costo total: the single module that decides the price of a Consumo.

One public operation, `CostoTotal.calculate`. It owns Asignación selection,
Fecha efectiva, season rule, segmentation, proration, staged filling
(ADR-0003) and taxes. Its only seam is a `TariffCatalog`. Raises domain
errors only; HTTP translation belongs to the caller.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol, Sequence

from services.business.period_utils import (
    MonthSegment,
    midpoint_date,
    split_by_month_segments,
)

IVA_RATE = Decimal("0.16")
DAP_RATE = Decimal("0.05")

_SUMMER_MONTHS = range(4, 10)  # Apr-Sep
_MIN_MINORITY_DAYS = 15
# Ranges store MONTHLY limits; a midpoint segment bills a ~60-day period.
MIDPOINT_PERIOD_FACTOR = Decimal("2")


class CostoTotalError(Exception):
    """Base domain error."""


class ViviendaNotFound(CostoTotalError):
    pass


class PeriodoNotFound(CostoTotalError):
    pass


class NoAsignacionVigente(CostoTotalError):
    pass


class VersionNotFound(CostoTotalError):
    pass


class RangosNotFound(CostoTotalError):
    pass


class TariffCatalog(Protocol):
    def vivienda(self, vivienda_id: int) -> Any: ...
    def periodo(self, periodo_id: int) -> Any: ...
    def asignaciones(self, vivienda_id: int) -> Sequence[Any]:
        """Asignaciones of a Vivienda, most recent first."""
    def tarifa(self, tariff_id: int) -> Any: ...
    def version(self, tariff_id: int, year: int, month: int) -> Any:
        """Versión of that month, else the most recent earlier one, else None."""
    def rangos(self, version_id: int) -> Sequence[Any]: ...


@dataclass
class Renglon:
    """One Rango within one segment."""
    segment_year: int
    segment_month: int
    tier_level: int
    tier_name: str
    days_in_segment: int
    prorated_kwh_capacity: Optional[Decimal]  # None -> unlimited
    kwh_charged: Decimal
    price_per_kwh: Decimal
    subtotal: Decimal


@dataclass
class Desglose:
    tariff_id: int
    tariff_code: str
    renglones: List[Renglon]
    costo_base: Decimal
    iva: Decimal
    dap: Decimal
    costo_total: Decimal
    cost_per_kwh: Decimal  # 0 when Consumo is 0


@dataclass
class _SegmentoRango:
    segment: MonthSegment
    tier_level: int
    price_per_kwh: Decimal
    capacity: Optional[Decimal]
    kwh_charged: Decimal = field(default_factory=lambda: Decimal("0"))


def _tier_names(max_level: int) -> Dict[int, str]:
    if max_level <= 0:
        return {}
    names = {1: "Básico"}
    for level in range(2, max_level):
        names[level] = f"Intermedio{level - 1}" if level > 2 else "Intermedio"
    names[max_level] = "Excedente"
    return names


class CostoTotal:
    def __init__(self, catalog: TariffCatalog) -> None:
        self.catalog = catalog

    def calculate(
        self,
        consumo: Decimal,
        vivienda_id: int,
        start_date: date,
        end_date: date,
        periodo_id: Optional[int] = None,
    ) -> Desglose:
        """Costo total of `consumo` over [start_date, end_date].

        With a Periodo, its end date replaces `end_date` for Fecha efectiva
        and segmentation (it is read once). Without one, the range is used.
        """
        if self.catalog.vivienda(vivienda_id) is None:
            raise ViviendaNotFound(f"Household not found: {vivienda_id}")
        if periodo_id is not None:
            periodo = self.catalog.periodo(periodo_id)
            if periodo is None:
                raise PeriodoNotFound(f"Billing period not found: {periodo_id}")
            end_date = periodo.end_date

        efectiva = midpoint_date(start_date, end_date)
        tariff_id, code = self._asignacion_vigente(vivienda_id, efectiva)
        segmento_rangos = self._segmento_rangos(self._segments(start_date, end_date), tariff_id)
        self._fill_segments(segmento_rangos, consumo)
        return self._desglose(segmento_rangos, tariff_id, code, consumo)

    # -- Asignación ---------------------------------------------------

    def _asignacion_vigente(self, vivienda_id: int, efectiva: date):
        for a in self.catalog.asignaciones(vivienda_id):
            if a.start_date <= efectiva and (a.end_date is None or a.end_date >= efectiva):
                tarifa = self.catalog.tarifa(a.tariff_id)
                if tarifa is None:
                    continue
                if self.catalog.version(a.tariff_id, efectiva.year, efectiva.month) is None:
                    continue
                return a.tariff_id, tarifa.code
        raise NoAsignacionVigente("No active tariff for this period")

    # -- Segments -----------------------------------------------------

    @staticmethod
    def _midpoint_segment(start: date, end: date) -> MonthSegment:
        mid = midpoint_date(start, end)
        days = (end - start).days + 1
        return MonthSegment(
            year=mid.year, month=mid.month, calendar_days=days, segment_days=days,
            start_date=start, end_date=end, capacity_factor=MIDPOINT_PERIOD_FACTOR,
        )

    def _segments(self, start: date, end: date) -> List[MonthSegment]:
        if (start.month in _SUMMER_MONTHS) == (end.month in _SUMMER_MONTHS):
            return [self._midpoint_segment(start, end)]
        segments = split_by_month_segments(start, end)
        summer = sum(s.segment_days for s in segments if s.month in _SUMMER_MONTHS)
        other = sum(s.segment_days for s in segments if s.month not in _SUMMER_MONTHS)
        if min(summer, other) < _MIN_MINORITY_DAYS:
            return [self._midpoint_segment(start, end)]
        return segments

    def _segmento_rangos(self, segments: List[MonthSegment], tariff_id: int) -> List[_SegmentoRango]:
        segmento_rangos: List[_SegmentoRango] = []
        for seg in segments:
            version = self.catalog.version(tariff_id, seg.year, seg.month)
            if not version:
                raise VersionNotFound(
                    f"No tariff version found for tariff_id={tariff_id} "
                    f"year={seg.year} month={seg.month}"
                )
            ranges = self.catalog.rangos(version.id)
            if not ranges:
                raise RangosNotFound(
                    f"No tariff ranges configured for tariff_version_id={version.id}"
                )
            cal = Decimal(seg.calendar_days)
            seg_d = Decimal(seg.segment_days)
            for i, tr in enumerate(sorted(ranges, key=lambda r: r.range_min)):
                capacity = (
                    None if tr.range_max is None
                    else (tr.range_max - tr.range_min) / cal * seg_d * Decimal(seg.capacity_factor)
                )
                segmento_rangos.append(_SegmentoRango(seg, i + 1, tr.price_per_kwh, capacity))
        return segmento_rangos

    # -- Filling (ADR-0003) -------------------------------------------

    def _fill_segments(self, segmento_rangos: List[_SegmentoRango], consumo: Decimal) -> None:
        grouped: Dict[Any, List[_SegmentoRango]] = defaultdict(list)
        for s in segmento_rangos:
            seg = s.segment
            grouped[(seg.year, seg.month, seg.start_date, seg.end_date)].append(s)
        if len(grouped) <= 1:
            self._fill_tiers(segmento_rangos, consumo)
            return

        keys = sorted(grouped)
        for k in keys:
            grouped[k].sort(key=lambda s: s.tier_level)
        total_days = sum(Decimal(grouped[k][0].segment.segment_days) for k in keys)
        if total_days <= 0:
            return
        allocated = Decimal("0")
        for i, k in enumerate(keys):
            if i == len(keys) - 1:  # last segment absorbs the remainder
                part = max(Decimal("0"), consumo - allocated)
            else:
                part = consumo * Decimal(grouped[k][0].segment.segment_days) / total_days
                allocated += part
            self._fill_tiers(grouped[k], part)

    @staticmethod
    def _fill_tiers(segmento_rangos: List[_SegmentoRango], consumo: Decimal) -> None:
        levels: Dict[int, List[_SegmentoRango]] = defaultdict(list)
        for s in segmento_rangos:
            levels[s.tier_level].append(s)
        remaining = consumo
        for level in sorted(levels):
            if remaining <= 0:
                break
            finite = [s for s in levels[level] if s.capacity is not None]
            infinite = [s for s in levels[level] if s.capacity is None]
            if not infinite:
                total_cap = sum(s.capacity for s in finite)
                energy = min(remaining, total_cap)
                remaining -= energy
                if total_cap > 0:
                    for s in finite:
                        s.kwh_charged = energy * s.capacity / total_cap
            else:
                for s in finite:
                    s.kwh_charged = min(remaining, s.capacity)
                    remaining -= s.kwh_charged
                days = sum(Decimal(s.segment.segment_days) for s in infinite)
                for s in infinite:
                    if days > 0:
                        s.kwh_charged = remaining * Decimal(s.segment.segment_days) / days
                remaining = Decimal("0")

    # -- Result -------------------------------------------------------

    @staticmethod
    def _desglose(segmento_rangos: List[_SegmentoRango], tariff_id: int, code: str, consumo: Decimal) -> Desglose:
        names = _tier_names(max((s.tier_level for s in segmento_rangos), default=0))
        renglones = [
            Renglon(
                segment_year=s.segment.year,
                segment_month=s.segment.month,
                tier_level=s.tier_level,
                tier_name=names.get(s.tier_level, f"Nivel {s.tier_level}"),
                days_in_segment=s.segment.segment_days,
                prorated_kwh_capacity=s.capacity,
                kwh_charged=s.kwh_charged,
                price_per_kwh=s.price_per_kwh,
                subtotal=s.kwh_charged * s.price_per_kwh,
            )
            for s in segmento_rangos
        ]
        base = Decimal("0")
        for r in renglones:
            base += r.subtotal
        iva, dap = base * IVA_RATE, base * DAP_RATE
        return Desglose(
            tariff_id=tariff_id, tariff_code=code, renglones=renglones,
            costo_base=base, iva=iva, dap=dap, costo_total=base + iva + dap,
            cost_per_kwh=base / consumo if consumo > 0 else Decimal("0"),
        )
