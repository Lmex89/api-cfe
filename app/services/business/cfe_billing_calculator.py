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

def _get_tier_names(max_level: int) -> Dict[int, str]:
    """Return CFE-style tier names based on the number of tariff ranges.

    Last level is always Excedente; middle levels are Intermedio, Intermedio2, etc.
    Examples:
      2 levels -> Básico, Excedente
      3 levels -> Básico, Intermedio, Excedente
      4 levels -> Básico, Intermedio, Intermedio2, Excedente
    """
    if max_level <= 0:
        return {}
    names: Dict[int, str] = {1: "Básico"}
    for level in range(2, max_level):
        suffix = level - 1
        names[level] = f"Intermedio{suffix}" if suffix > 1 else "Intermedio"
    names[max_level] = "Excedente"
    return names

_SUMMER_START_MONTH = 4
_SUMMER_END_MONTH = 9

# Billing periods are bimonthly (~60 days). tariff_ranges store MONTHLY tier
# limits (as scraped), so single-segment (midpoint) billing — which applies one
# month's prices to the whole period without monthly scaling — must double the
# tier capacity to match the 60-day period. Per-month segments keep the stored
# monthly limits and prorate them by calendar days.
MIDPOINT_PERIOD_FACTOR = Decimal("2")


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
            summer_days = sum(
                s.segment_days for s in segments if self._is_summer_month(s.month)
            )
            non_summer_days = sum(
                s.segment_days for s in segments if not self._is_summer_month(s.month)
            )
            minority_days = min(summer_days, non_summer_days)

            logger.info(
                f"Cross-season period detected: total_days={(end_date - start_date).days + 1}, "
                f"summer_days={summer_days}, non_summer_days={non_summer_days}, "
                f"minority_days={minority_days}"
            )

            if minority_days < 15:
                segments = [self._build_midpoint_segment(start_date, end_date)]
                logger.info(
                    f"Minority season < 15 days ({minority_days}). "
                    f"Falling back to single-segment midpoint pricing."
                )
            else:
                logger.info(
                    f"Minority season >= 15 days ({minority_days}). "
                    f"Using per-month prorated segmentation."
                )

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

            logger.debug(
                f"Segment {seg.year}-{seg.month:02d}: calendar_days={cal}, "
                f"segment_days={seg_d}, ratio={seg_d / cal if cal > 0 else 0}"
            )

            for i, tr in enumerate(sorted_ranges):
                tier_level = i + 1

                if tr.range_max is not None:
                    range_size = tr.range_max - tr.range_min
                    capacity: Optional[Decimal] = (
                        range_size / cal * seg_d * Decimal(seg.capacity_factor)
                    )
                    logger.debug(
                        f"Capacity proration: range_min={tr.range_min}, "
                        f"range_max={tr.range_max}, range_size={range_size}, "
                        f"calendar_days={cal}, segment_days={seg_d}, "
                        f"capacity_factor={seg.capacity_factor}, "
                        f"prorated_capacity={range_size} / {cal} * {seg_d} * "
                        f"{seg.capacity_factor} = {capacity}"
                    )
                else:
                    capacity = None  # unlimited
                    logger.debug(
                        f"Unlimited tier (last): range_min={tr.range_min}, "
                        f"range_max=None, capacity=unlimited"
                    )

                slots.append(
                    _ProratedSlot(
                        segment=seg,
                        tier_level=tier_level,
                        price_per_kwh=tr.price_per_kwh,
                        capacity=capacity,
                    )
                )
                logger.debug(
                    f"Slot created: seg={seg.year}/{seg.month} tier={tier_level} "
                    f"capacity={capacity} price={tr.price_per_kwh}"
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
                logger.debug(
                    f"Segment allocation (last): seg={key[0]}/{key[1]:02d} "
                    f"days={segment_days}, remaining after previous: "
                    f"{consumption_kwh} - {allocated} = {segment_consumption}"
                )
            else:
                segment_consumption = (consumption_kwh * segment_days) / total_days
                logger.debug(
                    f"Segment allocation: seg={key[0]}/{key[1]:02d} "
                    f"days={segment_days}/{total_days}, formula: "
                    f"{consumption_kwh} * {segment_days} / {total_days} = {segment_consumption}"
                )
                allocated += segment_consumption
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
        # period without monthly-capacity scaling. Ranges store monthly limits,
        # so scale them up for the ~60-day billing period convention.
        calendar_days = segment_days
        return MonthSegment(
            year=midpoint.year,
            month=midpoint.month,
            calendar_days=calendar_days,
            segment_days=segment_days,
            start_date=start_date,
            end_date=end_date,
            capacity_factor=MIDPOINT_PERIOD_FACTOR,
        )

    def _fill_sequentially(
        self, slots: List[_ProratedSlot], consumption_kwh: Decimal
    ) -> None:
        """Mutate each slot's kwh_charged by filling cheapest tier levels first."""
        tier_groups: Dict[int, List[_ProratedSlot]] = defaultdict(list)
        for slot in slots:
            tier_groups[slot.tier_level].append(slot)

        max_level = max((slot.tier_level for slot in slots), default=0)
        tier_names = _get_tier_names(max_level)
        remaining = consumption_kwh

        for level in sorted(tier_groups.keys()):
            if remaining <= Decimal("0"):
                break

            level_slots = tier_groups[level]
            finite = [s for s in level_slots if s.capacity is not None]
            infinite = [s for s in level_slots if s.capacity is None]

            if not infinite:
                total_cap = sum(s.capacity for s in finite)  # type: ignore[misc]
                energy = min(remaining, total_cap)
                remaining -= energy

                logger.debug(
                    f"Tier {level} ({tier_names.get(level, f'Nivel {level}')}): all finite slots, "
                    f"total_cap={total_cap}, requesting={remaining + energy}, "
                    f"filling={energy}, remaining={remaining}"
                )

                if total_cap > Decimal("0"):
                    for s in finite:
                        s.kwh_charged = energy * s.capacity / total_cap  # type: ignore[operator]
                        logger.debug(
                            f"  Slot seg={s.segment.year}/{s.segment.month:02d} "
                            f"tier={s.tier_level}: "
                            f"{energy} * {s.capacity} / {total_cap} = {s.kwh_charged} kWh"
                        )
            else:
                for s in finite:
                    charged = min(remaining, s.capacity)  # type: ignore[arg-type]
                    s.kwh_charged = charged
                    remaining -= charged
                    logger.debug(
                        f"  Finite slot seg={s.segment.year}/{s.segment.month:02d} "
                        f"tier={s.tier_level}: capacity={s.capacity}, "
                        f"min(remaining_before={remaining + charged}, cap={s.capacity}) "
                        f"= {charged} kWh consumed"
                    )

                total_days = sum(
                    Decimal(s.segment.segment_days) for s in infinite
                )
                logger.debug(
                    f"  Infinite slots: total_days={total_days}, "
                    f"remaining_kwh={remaining}"
                )
                for s in infinite:
                    if total_days > Decimal("0"):
                        s.kwh_charged = remaining * Decimal(s.segment.segment_days) / total_days
                        logger.debug(
                            f"  Infinite slot seg={s.segment.year}/{s.segment.month:02d} "
                            f"tier={s.tier_level}: "
                            f"{remaining} * {s.segment.segment_days} / {total_days} "
                            f"= {s.kwh_charged} kWh"
                        )

                remaining = Decimal("0")

            logger.debug(
                f"Tier {level} ({tier_names.get(level, f'Nivel {level}')}) final: remaining={remaining} kWh"
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

        max_level = max((slot.tier_level for slot in slots), default=0)
        tier_names = _get_tier_names(max_level)

        for slot in slots:
            line_subtotal = slot.kwh_charged * slot.price_per_kwh
            subtotal += line_subtotal

            logger.debug(
                f"Line item: seg={slot.segment.year}/{slot.segment.month:02d} "
                f"tier={slot.tier_level} ({tier_names.get(slot.tier_level, '?')}), "
                f"kwh={slot.kwh_charged} × price={slot.price_per_kwh} = {line_subtotal}"
            )

            tier_lines.append(
                CfeTierLineItem(
                    segment_year=slot.segment.year,
                    segment_month=slot.segment.month,
                    tier_level=slot.tier_level,
                    tier_name=tier_names.get(slot.tier_level, f"Nivel {slot.tier_level}"),
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
            f"CFE breakdown built: subtotal_before_taxes={subtotal}, "
            f"iva (16%) = {subtotal} × 0.16 = {iva}, "
            f"dap (5%) = {subtotal} × 0.05 = {dap}, "
            f"total = {subtotal} + {iva} + {dap} = {subtotal + iva + dap}"
        )

        return CfeBillingBreakdownResponse(
            tier_lines=tier_lines,
            subtotal_before_taxes=float(subtotal),
            iva=float(iva),
            dap=float(dap),
            total=float(subtotal + iva + dap),
        )
