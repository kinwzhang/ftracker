from collections import namedtuple
from datetime import date, timedelta

Holiday = namedtuple("Holiday", ["date", "name"])

# HK general holidays by year, with the OFFICIALLY observed date (the actual
# festival date may differ when it falls on a weekend, in which case the
# spec'd ``day-following / day-after`` date is the observed holiday).
#
# Source: HK Government Gazette — General Holidays for 2026 / 2027, as
# recorded in feat_requirements/20260710_enhancement.md (B5).
# Year-by-year lookup keeps the per-holiday logic simple and avoids lunar
# calendar computation. Extend the table below as new official years arrive.
_HK_HOLIDAYS_BY_YEAR = {
    2025: (
        (date(2025, 1, 1), "New Year's Day"),
        (date(2025, 1, 29), "Lunar New Year"),
        (date(2025, 1, 30), "Lunar New Year"),
        (date(2025, 1, 31), "Lunar New Year"),
        (date(2025, 4, 4), "Ching Ming Festival"),
        (date(2025, 4, 18), "Good Friday"),
        (date(2025, 4, 19), "The day following Good Friday"),
        (date(2025, 4, 21), "Easter Monday"),
        (date(2025, 5, 1), "Labour Day"),
        (date(2025, 5, 5), "The Birthday of the Buddha"),
        (date(2025, 5, 31), "Tuen Ng Festival"),
        (date(2025, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2025, 10, 1), "National Day"),
        (date(2025, 10, 7),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2025, 10, 29), "Chung Yeung Festival"),
        (date(2025, 12, 25), "Christmas Day"),
        (date(2025, 12, 26), "The first weekday after Christmas Day"),
    ),
    2026: (
        (date(2026, 1, 1), "New Year's Day"),
        (date(2026, 2, 17), "Lunar New Year"),
        (date(2026, 2, 18), "Lunar New Year"),
        (date(2026, 2, 19), "Lunar New Year"),
        (date(2026, 4, 3), "Good Friday"),
        (date(2026, 4, 4), "The day following Good Friday"),
        (date(2026, 4, 6), "The day following Ching Ming Festival"),
        (date(2026, 4, 7), "The day following Easter Monday"),
        (date(2026, 5, 1), "Labour Day"),
        (date(2026, 5, 25),
         "The day following the Birthday of the Buddha"),
        (date(2026, 6, 19), "Tuen Ng Festival"),
        (date(2026, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2026, 9, 26),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2026, 10, 1), "National Day"),
        (date(2026, 10, 19),
         "The day following Chung Yeung Festival"),
        (date(2026, 12, 25), "Christmas Day"),
        (date(2026, 12, 26), "The first weekday after Christmas Day"),
    ),
    2027: (
        (date(2027, 1, 1), "New Year's Day"),
        (date(2027, 2, 6), "Lunar New Year"),
        (date(2027, 2, 8), "Lunar New Year"),
        (date(2027, 2, 9), "Lunar New Year"),
        (date(2027, 3, 26), "Good Friday"),
        (date(2027, 3, 27), "The day following Good Friday"),
        (date(2027, 3, 29), "Easter Monday"),
        (date(2027, 4, 5), "Ching Ming Festival"),
        (date(2027, 5, 1), "Labour Day"),
        (date(2027, 5, 13), "The Birthday of the Buddha"),
        (date(2027, 6, 9), "Tuen Ng Festival"),
        (date(2027, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2027, 9, 16),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2027, 10, 1), "National Day"),
        (date(2027, 10, 8), "Chung Yeung Festival"),
        (date(2027, 12, 25), "Christmas Day"),
        (date(2027, 12, 27), "The first weekday after Christmas Day"),
    ),
    # Years 2028-2030 below are placeholders calibrated from the project's
    # initial implementation; replace with gazetted data when available.
    2028: (
        (date(2028, 1, 1), "New Year's Day"),
        (date(2028, 1, 26), "Lunar New Year"),
        (date(2028, 1, 27), "Lunar New Year"),
        (date(2028, 1, 28), "Lunar New Year"),
        (date(2028, 4, 4), "Ching Ming Festival"),
        (date(2028, 4, 14), "Good Friday"),
        (date(2028, 4, 15), "The day following Good Friday"),
        (date(2028, 4, 17), "Easter Monday"),
        (date(2028, 5, 1), "Labour Day"),
        (date(2028, 5, 2), "The Birthday of the Buddha"),
        (date(2028, 5, 29), "Tuen Ng Festival"),
        (date(2028, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2028, 10, 1), "National Day"),
        (date(2028, 10, 4),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2028, 10, 26), "Chung Yeung Festival"),
        (date(2028, 12, 25), "Christmas Day"),
        (date(2028, 12, 26), "The first weekday after Christmas Day"),
    ),
    2029: (
        (date(2029, 1, 1), "New Year's Day"),
        (date(2029, 2, 13), "Lunar New Year"),
        (date(2029, 2, 14), "Lunar New Year"),
        (date(2029, 2, 15), "Lunar New Year"),
        (date(2029, 4, 4), "Ching Ming Festival"),
        (date(2029, 4, 6), "Good Friday"),
        (date(2029, 4, 7), "The day following Good Friday"),
        (date(2029, 4, 9), "Easter Monday"),
        (date(2029, 5, 1), "Labour Day"),
        (date(2029, 5, 21), "The Birthday of the Buddha"),
        (date(2029, 6, 16), "Tuen Ng Festival"),
        (date(2029, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2029, 9, 22),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2029, 10, 1), "National Day"),
        (date(2029, 10, 15), "Chung Yeung Festival"),
        (date(2029, 12, 25), "Christmas Day"),
        (date(2029, 12, 26), "The first weekday after Christmas Day"),
    ),
    2030: (
        (date(2030, 1, 1), "New Year's Day"),
        (date(2030, 2, 3), "Lunar New Year"),
        (date(2030, 2, 4), "Lunar New Year"),
        (date(2030, 2, 5), "Lunar New Year"),
        (date(2030, 4, 5), "Ching Ming Festival"),
        (date(2030, 4, 19), "Good Friday"),
        (date(2030, 4, 20), "The day following Good Friday"),
        (date(2030, 4, 22), "Easter Monday"),
        (date(2030, 5, 1), "Labour Day"),
        (date(2030, 5, 11), "The Birthday of the Buddha"),
        (date(2030, 6, 6), "Tuen Ng Festival"),
        (date(2030, 7, 1),
         "Hong Kong Special Administrative Region Establishment Day"),
        (date(2030, 9, 12),
         "The day following the Chinese Mid-Autumn Festival"),
        (date(2030, 10, 1), "National Day"),
        (date(2030, 10, 5), "Chung Yeung Festival"),
        (date(2030, 12, 25), "Christmas Day"),
        (date(2030, 12, 26), "The first weekday after Christmas Day"),
    ),
}


def hk_public_holidays(year: int) -> set[date]:
    return {h.date for h in hk_public_holidays_named(year)}


def hk_public_holidays_named(year: int) -> list[Holiday]:
    return [Holiday(d, name) for d, name in _HK_HOLIDAYS_BY_YEAR.get(year, ())]


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in hk_public_holidays(d.year)


def calculate_scheduled_date(month_start: date, sla_days: int, sla_type: str) -> date:
    """Compute a task's scheduled (due) date from its SLA.

    ``month_start`` is the 1st of the month the task belongs to.

    Two SLA semantics are supported:

      * ``"Calendar Day"`` — ``sla_days`` is the **day of the month**.
        ``sla_days = 1`` → 1st of the month, ``sla_days = 13`` → 13th of the
        month, etc. Pins to an exact calendar day regardless of weekends or
        public holidays (B10). Values outside the month's range are clamped
        to the last day of the month; ``sla_days <= 0`` falls back to
        ``month_start``.
      * ``"Working Day"`` (or any other value) — counts forward from
        ``month_start`` and skips weekends + HK public holidays.
        ``sla_days = 0`` returns ``month_start`` (the task is due on day 1
        regardless of whether that's a business day); ``sla_days = 1`` returns
        the first business day on or after ``month_start``.
    """
    if sla_type == "Calendar Day":
        if sla_days <= 0:
            return month_start
        # day-of-month: sla_days = 1 → day 1, sla_days = 13 → day 13.
        try:
            return month_start.replace(day=sla_days)
        except ValueError:
            # Day out of range for the month (e.g. Feb 30) → clamp to last day.
            from calendar import monthrange
            last_day = monthrange(month_start.year, month_start.month)[1]
            return month_start.replace(day=last_day)

    current = month_start
    business_days_counted = 0
    while business_days_counted < sla_days:
        if is_business_day(current):
            business_days_counted += 1
            if business_days_counted == sla_days:
                break
        current += timedelta(days=1)
    return current
