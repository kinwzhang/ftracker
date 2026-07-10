from collections import namedtuple
from datetime import date, timedelta

Holiday = namedtuple("Holiday", ["date", "name"])


def hk_public_holidays(year: int) -> set[date]:
    return {h.date for h in hk_public_holidays_named(year)}


def hk_public_holidays_named(year: int) -> list[Holiday]:
    holidays = []

    holidays.extend(_fixed_holidays(year))
    holidays.extend(_lunar_new_year(year))
    holidays.extend(_ching_ming(year))
    holidays.extend(_easter_monday(year))
    holidays.extend(_buddha_birthday(year))
    holidays.extend(_dragon_boat(year))
    holidays.extend(_mid_autumn(year))
    holidays.extend(_chung_yeung(year))
    holidays.extend(_christmas_related(year))

    return holidays


def _fixed_holidays(year: int) -> list[Holiday]:
    return [
        Holiday(date(year, 1, 1), "New Year's Day"),
        Holiday(date(year, 7, 1), "HKSAR Establishment Day"),
        Holiday(date(year, 10, 1), "National Day"),
        Holiday(date(year, 12, 25), "Christmas Day"),
        Holiday(date(year, 12, 26), "Boxing Day"),
    ]


def _lunar_new_year(year: int) -> list[Holiday]:
    known = {
        2025: [date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31)],
        2026: [date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19)],
        2027: [date(2027, 2, 6), date(2027, 2, 7), date(2027, 2, 8)],
        2028: [date(2028, 1, 26), date(2028, 1, 27), date(2028, 1, 28)],
        2029: [date(2029, 2, 13), date(2029, 2, 14), date(2029, 2, 15)],
        2030: [date(2030, 2, 3), date(2030, 2, 4), date(2030, 2, 5)],
    }
    return [Holiday(d, "Lunar New Year") for d in known.get(year, [])]


def _ching_ming(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 4, 4),
        2026: date(2026, 4, 5),
        2027: date(2027, 4, 5),
        2028: date(2028, 4, 4),
        2029: date(2029, 4, 4),
        2030: date(2030, 4, 5),
    }
    d = known.get(year)
    return [Holiday(d, "Ching Ming Festival")] if d else []


def _easter_monday(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 4, 21),
        2026: date(2026, 4, 6),
        2027: date(2027, 3, 29),
        2028: date(2028, 4, 17),
        2029: date(2029, 4, 2),
        2030: date(2030, 4, 22),
    }
    d = known.get(year)
    return [Holiday(d, "Easter Monday")] if d else []


def _buddha_birthday(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 5, 5),
        2026: date(2026, 5, 25),
        2027: date(2027, 5, 14),
        2028: date(2028, 5, 2),
        2029: date(2029, 5, 21),
        2030: date(2030, 5, 11),
    }
    d = known.get(year)
    return [Holiday(d, "Buddha's Birthday")] if d else []


def _dragon_boat(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 5, 31),
        2026: date(2026, 6, 19),
        2027: date(2027, 6, 9),
        2028: date(2028, 5, 29),
        2029: date(2029, 6, 16),
        2030: date(2030, 6, 6),
    }
    d = known.get(year)
    return [Holiday(d, "Dragon Boat Festival")] if d else []


def _mid_autumn(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 10, 7),
        2026: date(2026, 9, 27),
        2027: date(2027, 9, 16),
        2028: date(2028, 10, 4),
        2029: date(2029, 9, 22),
        2030: date(2030, 9, 12),
    }
    d = known.get(year)
    return [Holiday(d, "Mid-Autumn Festival")] if d else []


def _chung_yeung(year: int) -> list[Holiday]:
    known = {
        2025: date(2025, 10, 29),
        2026: date(2026, 10, 18),
        2027: date(2027, 10, 8),
        2028: date(2028, 10, 26),
        2029: date(2029, 10, 15),
        2030: date(2030, 10, 5),
    }
    d = known.get(year)
    return [Holiday(d, "Chung Yeung Festival")] if d else []


def _christmas_related(year: int) -> list[Holiday]:
    return []


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in hk_public_holidays(d.year)


def calculate_scheduled_date(month_start: date, sla_days: int, sla_type: str) -> date:
    if sla_type == "Calendar Day":
        return month_start + timedelta(days=sla_days)

    current = month_start
    business_days_counted = 0
    while business_days_counted < sla_days:
        if is_business_day(current):
            business_days_counted += 1
            if business_days_counted == sla_days:
                break
        current += timedelta(days=1)
    return current
