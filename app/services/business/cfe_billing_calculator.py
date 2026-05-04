"""CFE SICOM sequential billing calculator.

Implements the 'Llenado Secuencial de Escalones Prorrateados' algorithm:
1. If the billing period is fully within summer (Apr-Sep) or fully outside summer,
   use midpoint month pricing for the whole period.
2. If the period crosses summer/non-summer, split into per-calendar-month segments.
3. Prorate each tier's capacity by the segment's days vs. the full calendar month.
4. Fill tiers sequentially inside each segment (Básico -> Intermedio -> Excedente).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from loguru import logger

from common.api.errors.business_error import TariffCalculationError
from model.dashboard_serializers import CfeBillingBreakdownResponse, CfeTierLineItem
from services.business.period_utils import MonthSegment, midpoint_date, split_by_month_segments
from starlette import status

if TYPE_CHECKING:
    from db.uow import TariffConsumptionUnitofWork

_TIER_NAMES: Dict[int, str] = {
    1: "Básico",
    2: "Intermedio",
    3: "Excedente",
}

_SUMMER_START_MONTH = 4
_SUMMER_END_MONTH = 9


@dataclass
class _ProratedSlot:
    """Internal representation of one tier within one month segment."""
    segment: MonthSegment
    tier_level: int
    price_per_kwh: Decimal
    capacity: Optional[Decimal]          # None → unlimited (last tier)
    kwh_charged: Decimal = field(default_factory=lambda: Decimal("0"))


class CfeSequentialBillingCalculator:
    """
    Calculates CFE billing cost using the prorated sequential tier-fill algorithm.

    Designed as a drop-in replacement for RangeBasedTariffCalculator but receives
    the full date range instead of a single effective date so it can split the
    period into monthly segments and apply per-month tariff versions.
    """

    def __init__(self, uow: "TariffConsumptionUnitofWork") -> None:
        self.uow = uow
        logger.info("CfeSequentialBillingCalculator initialized")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def calculate_cost(
        self,
        consumption_kwh: Decimal,
        tariff_id: int,
        start_date: date,
        end_date: date,
    ) -> CfeBillingBreakdownResponse:
        """
        Apply the CFE sequential prorated-tier algorithm and return a full
        breakdown response including per-segment, per-tier line items plus taxes.
        """
        logger.info(
            f"CFE billing calc: tariff_id={tariff_id}, "
            f"start={start_date}, end={end_date}, consumption={consumption_kwh} kWh"
        )

        if self._is_single_season_period(start_date, end_date):
            segments = [self._build_midpoint_segment(start_date, end_date)]
            logger.debug(
                f"Single-season billing period detected. Using midpoint month pricing: "
                f"segment={segments[0].year}-{segments[0].month:02d}, days={segments[0].segment_days}"
            )
        else:
            segments = split_by_month_segments(start_date, end_date)
            logger.debug("Cross-season billing period detected. Using per-month proration")

        logger.debug(f"Month segments: {[(s.year, s.month, s.segment_days) for s in segments]}")

        slots = self._build_prorated_slots(segments, tariff_id)
        self._fill_by_segment_or_single(slots, consumption_kwh)

        return self._build_response(slots)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prorated_slots(
        self, segments: List[MonthSegment], tariff_id: int
    ) -> List[_ProratedSlot]:
        """For every (segment, tariff range) pair, create a prorated slot."""
        slots: List[_ProratedSlot] = []

        for seg in segments:
            version = self.uow.tariff_version_repository.get_by_tariff_and_period_or_latest_before(
                tariff_id, seg.year, seg.month
            )
            if not version:
                raise TariffCalculationError(
                    f"No tariff version found for tariff_id={tariff_id} "
                    f"year={seg.year} month={seg.month}",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            if version.year != seg.year or version.month != seg.month:
                logger.debug(
                    f"Using fallback tariff version for segment {seg.year}-{seg.month:02d}: "
                    f"tariff_id={tariff_id}, version_id={version.id}, "
                    f"version_period={version.year}-{version.month:02d}"
                )

            ranges = self.uow.tariff_range_repository.list(
                tariff_version_id=version.id
            )
            if not ranges:
                raise TariffCalculationError(
                    f"No tariff ranges configured for tariff_version_id={version.id}",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            sorted_ranges = sorted(ranges, key=lambda r: r.range_min)
            cal = Decimal(seg.calendar_days)
            seg_d = Decimal(seg.segment_days)

            for i, tr in enumerate(sorted_ranges):
                tier_level = i + 1

                if tr.range_max is not None:
                    range_size = tr.range_max - tr.range_min
                    capacity: Optional[Decimal] = range_size / cal * seg_d
                else:
                    capacity = None  # unlimited

                slots.append(
                    _ProratedSlot(
                        segment=seg,
                        tier_level=tier_level,
                        price_per_kwh=tr.price_per_kwh,
                        capacity=capacity,
                    )
                )
                logger.debug(
                    f"Slot: seg={seg.year}/{seg.month} tier={tier_level} "
                    f"cap={capacity} price={tr.price_per_kwh}"
                )

        return slots

    def _fill_by_segment_or_single(
        self, slots: List[_ProratedSlot], consumption_kwh: Decimal
    ) -> None:
        """Apply mixed-period segment allocation or keep single-segment behavior."""
        segment_keys = {
            self._segment_key(slot.segment)
            for slot in slots
        }
        if len(segment_keys) <= 1:
            self._fill_sequentially(slots, consumption_kwh)
            return

        grouped = self._group_slots_by_segment(slots)
        ordered_keys = sorted(
            grouped.keys(),
            key=lambda key: (key[0], key[1], key[2], key[3]),
        )

        total_days = sum(
            Decimal(grouped[key][0].segment.segment_days)
            for key in ordered_keys
        )
        if total_days <= Decimal("0"):
            logger.warning("Skipping segment allocation because total_days is zero")
            return

        allocated = Decimal("0")
        last_index = len(ordered_keys) - 1

        for index, key in enumerate(ordered_keys):
            segment_slots = grouped[key]
            segment_days = Decimal(segment_slots[0].segment.segment_days)

            if index == last_index:
                segment_consumption = max(Decimal("0"), consumption_kwh - allocated)
            else:
                segment_consumption = (consumption_kwh * segment_days) / total_days
                allocated += segment_consumption

            logger.debug(
                f"Segment allocation: seg={key[0]}/{key[1]:02d} "
                f"start={key[2]} end={key[3]} days={segment_days} "
                f"segment_consumption={segment_consumption}"
            )
            self._fill_sequentially(segment_slots, segment_consumption)

    @staticmethod
    def _is_summer_month(month: int) -> bool:
        return _SUMMER_START_MONTH <= month <= _SUMMER_END_MONTH

    def _is_single_season_period(self, start_date: date, end_date: date) -> bool:
        start_is_summer = self._is_summer_month(start_date.month)
        end_is_summer = self._is_summer_month(end_date.month)
        return start_is_summer == end_is_summer

    def _build_midpoint_segment(self, start_date: date, end_date: date) -> MonthSegment:
        midpoint = midpoint_date(start_date, end_date)
        segment_days = (end_date - start_date).days + 1
        # In single-season midpoint mode, apply midpoint pricing to the whole
        # period without monthly-capacity scaling.
        calendar_days = segment_days
        return MonthSegment(
            year=midpoint.year,
            month=midpoint.month,
            calendar_days=calendar_days,
            segment_days=segment_days,
            start_date=start_date,
            end_date=end_date,
        )

    def _fill_sequentially(
        self, slots: List[_ProratedSlot], consumption_kwh: Decimal
    ) -> None:
        """Mutate each slot's kwh_charged by filling cheapest tier levels first."""
        tier_groups: Dict[int, List[_ProratedSlot]] = defaultdict(list)
        for slot in slots:
            tier_groups[slot.tier_level].append(slot)

        remaining = consumption_kwh

        for level in sorted(tier_groups.keys()):
            if remaining <= Decimal("0"):
                break

            level_slots = tier_groups[level]
            finite = [s for s in level_slots if s.capacity is not None]
            infinite = [s for s in level_slots if s.capacity is None]

            if not infinite:
                # All slots finite: fill the whole level then distribute
                total_cap = sum(s.capacity for s in finite)  # type: ignore[misc]
                energy = min(remaining, total_cap)
                remaining -= energy

                if total_cap > Decimal("0"):
                    for s in finite:
                        s.kwh_charged = energy * s.capacity / total_cap  # type: ignore[operator]
            else:
                # Finite slots absorb first, then infinite slots absorb the rest
                for s in finite:
                    charged = min(remaining, s.capacity)  # type: ignore[arg-type]
                    s.kwh_charged = charged
                    remaining -= charged

                total_days = sum(
                    Decimal(s.segment.segment_days) for s in infinite
                )
                for s in infinite:
                    if total_days > Decimal("0"):
                        s.kwh_charged = remaining * Decimal(s.segment.segment_days) / total_days

                remaining = Decimal("0")

            logger.debug(
                f"After filling tier {level}: remaining={remaining} kWh"
            )

    @staticmethod
    def _segment_key(segment: MonthSegment) -> Tuple[int, int, date, date]:
        return (segment.year, segment.month, segment.start_date, segment.end_date)

    def _group_slots_by_segment(
        self, slots: List[_ProratedSlot]
    ) -> Dict[Tuple[int, int, date, date], List[_ProratedSlot]]:
        grouped: Dict[Tuple[int, int, date, date], List[_ProratedSlot]] = defaultdict(list)
        for slot in slots:
            grouped[self._segment_key(slot.segment)].append(slot)

        for key_slots in grouped.values():
            key_slots.sort(key=lambda slot: slot.tier_level)

        return grouped

    def _build_response(self, slots: List[_ProratedSlot]) -> CfeBillingBreakdownResponse:
        """Aggregate filled slots into the response model."""
        tier_lines: List[CfeTierLineItem] = []
        subtotal = Decimal("0")

        for slot in slots:
            line_subtotal = slot.kwh_charged * slot.price_per_kwh
            subtotal += line_subtotal

            tier_lines.append(
                CfeTierLineItem(
                    segment_year=slot.segment.year,
                    segment_month=slot.segment.month,
                    tier_level=slot.tier_level,
                    tier_name=_TIER_NAMES.get(slot.tier_level, f"Nivel {slot.tier_level}"),
                    days_in_segment=slot.segment.segment_days,
                    prorated_kwh_capacity=(
                        float(slot.capacity) if slot.capacity is not None else None
                    ),
                    kwh_charged=float(slot.kwh_charged),
                    price_per_kwh=float(slot.price_per_kwh),
                    subtotal=float(line_subtotal),
                )
            )

        iva = subtotal * Decimal("0.16")
        dap = subtotal * Decimal("0.05")

        logger.info(
            f"CFE breakdown built: subtotal={subtotal}, iva={iva}, dap={dap}, "
            f"total={subtotal + iva + dap}"
        )

        return CfeBillingBreakdownResponse(
            tier_lines=tier_lines,
            subtotal_before_taxes=float(subtotal),
            iva=float(iva),
            dap=float(dap),
            total=float(subtotal + iva + dap),
        )
