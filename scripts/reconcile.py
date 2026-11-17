#!/usr/bin/env python3
"""Reconcile statement arithmetic and order/statement quantities using only stdlib.

Input is one JSON file; every number is read as an exact decimal. The script
reports findings and open items. It never corrects a source value.
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

# Major variable: truncation units tested against a statement's own line pattern.
TRUNCATION_UNITS = (Decimal(1), Decimal(10), Decimal(100), Decimal(1000))
# Major variable: Korean numerals for a printed written amount.
KOREAN_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
KOREAN_SMALL_UNITS = {"십": 10, "백": 100, "천": 1000}
KOREAN_BIG_UNITS = {"만": 10 ** 4, "억": 10 ** 8, "조": 10 ** 12}


def to_decimal(value, label="value"):
    """Method: convert text or integers to Decimal; binary floats are rejected."""
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{label} must be a decimal string or integer, not a float.")
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.replace(",", "").strip())
        except InvalidOperation:
            raise ValueError(f"{label} is not a decimal number.") from None
    raise ValueError(f"{label} must be a decimal string or integer.")


def text(value):
    """Method: render a Decimal without exponent notation or a trailing '.00'."""
    if value is None:
        return None
    if value == value.to_integral_value():
        return str(value.to_integral_value())
    return format(value, "f")


def finding(code, location, source, compared, cause, **extra):
    """Method: build one finding that keeps both values and their difference."""
    difference = None if source is None or compared is None else source - compared
    row = {"code": code, "location": location, "source_value": text(source),
           "compared_value": text(compared), "difference": text(difference), "cause": cause}
    row.update(extra)
    return row


def floor_to(value, unit):
    """Method: drop everything below the given unit."""
    return (value / unit).to_integral_value(rounding=ROUND_FLOOR) * unit


def parse_korean_amount(written):
    """Method: read a written amount such as '일금 삼백오십만 원정'; None if unreadable."""
    cleaned = "".join(str(written).split()).replace(",", "")
    if cleaned.startswith("일금"):
        cleaned = cleaned[2:]
    for suffix in ("원정", "원", "정"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    if not cleaned:
        return None
    total = section = number = 0
    for char in cleaned:
        if char in KOREAN_DIGITS:
            number = KOREAN_DIGITS[char]
        elif char in KOREAN_SMALL_UNITS:
            section += (number or 1) * KOREAN_SMALL_UNITS[char]
            number = 0
        elif char in KOREAN_BIG_UNITS:
            section += number
            total += (section or 1) * KOREAN_BIG_UNITS[char]
            section = number = 0
        else:
            return None
    return Decimal(total + section + number)


def check_lines(lines):
    """Method: recompute quantity x unit price and classify each line's difference."""
    rows, findings = [], []
    for index, line in enumerate(lines, 1):
        location = str(line.get("line_id", index))
        quantity = to_decimal(line.get("quantity"), f"line {location} quantity")
        price = to_decimal(line.get("unit_price"), f"line {location} unit_price")
        amount = to_decimal(line.get("amount"), f"line {location} amount")
        if amount is None:
            raise ValueError(f"line {location} needs an amount.")
        calculated = None if quantity is None or price is None else quantity * price
        rows.append((location, amount, calculated))
        if calculated is None:
            findings.append(finding("amount_not_checkable", location, amount, None,
                                    "The line has an amount but no quantity or unit price."))
    checkable = [row for row in rows if row[2] is not None]
    # Major variable: the smallest unit that explains every checkable line by truncation.
    unit = None
    if len(checkable) >= 2 and any(amount != calc for _, amount, calc in checkable):
        unit = next((u for u in TRUNCATION_UNITS
                     if all(amount == floor_to(calc, u) for _, amount, calc in checkable)), None)
    for location, amount, calculated in checkable:
        if amount == calculated:
            continue
        if unit is not None:
            findings.append(finding("amount_truncated", location, amount, calculated,
                                    f"Every line drops the amount below {text(unit)}.",
                                    truncation_unit=text(unit)))
        elif amount == calculated.quantize(Decimal(1), rounding=ROUND_HALF_UP):
            findings.append(finding("rounding_difference", location, amount, calculated,
                                    "The amount is the calculated value rounded to a whole unit."))
        else:
            findings.append(finding("amount_difference", location, amount, calculated,
                                    "The amount differs and no consistent rounding pattern explains it."))
    return {"lines_checked": len(checkable), "lines_not_checkable": len(rows) - len(checkable),
            "truncation_unit": text(unit), "line_sum": text(sum((row[1] for row in rows), Decimal(0)))}, findings


def check_totals(statement):
    """Method: check line sum, tax, total and written amount from stated values only."""
    findings, checks = [], {}
    line_sum = sum((to_decimal(line.get("amount")) for line in statement.get("lines", [])), Decimal(0))
    supply = to_decimal(statement.get("supply_amount"), "supply_amount")
    tax = to_decimal(statement.get("tax_amount"), "tax_amount")
    total = to_decimal(statement.get("total_amount"), "total_amount")
    rate = to_decimal(statement.get("tax_rate"), "tax_rate")

    def record(name, source, compared, code, cause):
        """Method: store pass/finding, or not_checkable when a value is missing."""
        if source is None or compared is None:
            checks[name] = "not_checkable"
        elif source == compared:
            checks[name] = "pass"
        else:
            checks[name] = "finding"
            findings.append(finding(code, name, source, compared, cause))

    record("supply_vs_line_sum", supply, line_sum, "total_difference",
           "The supply amount differs from the sum of the line amounts.")
    record("total_vs_supply_plus_tax", total,
           None if supply is None or tax is None else supply + tax, "total_difference",
           "The total differs from supply plus tax.")
    if rate is None:
        checks["tax_vs_rate"] = "not_checked"
    elif supply is None or tax is None:
        checks["tax_vs_rate"] = "not_checkable"
    else:
        expected = supply * rate
        accepted = {expected, floor_to(expected, Decimal(1)),
                    expected.quantize(Decimal(1), rounding=ROUND_HALF_UP)}
        checks["tax_vs_rate"] = "pass" if tax in accepted else "finding"
        if tax not in accepted:
            findings.append(finding("tax_difference", "tax_vs_rate", tax, expected,
                                    "The tax differs from supply times the stated rate."))
    written = statement.get("written_amount")
    if written is None:
        checks["written_amount"] = "not_checked"
    else:
        parsed = parse_korean_amount(written)
        record("written_amount", total, parsed, "written_amount_difference",
               "The written amount differs from the numeric total.")
    return checks, findings


def check_cumulative(rounds):
    """Method: compare each printed cumulative value with the running sum of rounds."""
    findings = []
    running = {"count": Decimal(0), "measure": Decimal(0)}
    for entry in rounds:
        for key in ("count", "measure"):
            value = to_decimal(entry.get(key), f"round {entry.get('round')} {key}")
            running[key] += value or Decimal(0)
            printed = to_decimal(entry.get(f"cumulative_{key}"))
            if printed is not None and printed != running[key]:
                findings.append(finding("cumulative_inconsistency",
                                        f"round {entry.get('round')} cumulative_{key}",
                                        printed, running[key],
                                        "The printed cumulative value differs from the sum of rounds."))
    return findings


def places(value):
    """Method: number of decimal places shown in a source value."""
    return max(0, -value.as_tuple().exponent)


def at_precision(value, digits):
    """Method: round a value to the other document's displayed precision."""
    return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def check_links(rounds, links):
    """Method: compare linked quantities and derive open items per billing group."""
    by_round = {str(entry.get("round")): entry for entry in rounds}
    findings, groups = [], {}
    for link in links:
        key = str(link.get("round"))
        if key not in by_round:
            raise ValueError(f"A link refers to unknown order round {key}.")
        groups.setdefault(link.get("group"), {}).setdefault(key, []).append(link)
        results = {}
        for name in ("count", "measure"):
            ordered = to_decimal(by_round[key].get(name))
            billed = to_decimal(link.get(f"statement_{name}"))
            if ordered is not None and billed is not None:
                same = at_precision(ordered, places(billed)) == billed
                results[name] = (ordered, billed, same)
                if same and ordered != billed:
                    findings.append(finding("rounding_difference",
                                            f"round {key} {name}", billed, ordered,
                                            "Values agree at the statement's displayed precision."))
        if len(results) == 2 and results["count"][2] and not results["measure"][2]:
            ordered, billed, _ = results["measure"]
            findings.append(finding("quantity_mismatch", f"round {key} measure", billed, ordered,
                                    "Piece counts agree but the measure differs beyond rounding."))
    open_items = []
    for group, linked in (groups or {None: {}}).items():
        for key, entry in by_round.items():
            items = linked.get(key, [])
            basis = "measure" if entry.get("measure") is not None and all(
                item.get("statement_measure") is not None for item in items) else "count"
            ordered = to_decimal(entry.get(basis))
            billed_values = [to_decimal(item.get(f"statement_{basis}")) for item in items]
            if ordered is None or None in billed_values:
                status, billed, remaining = "not_checkable", None, None
            else:
                billed = sum(billed_values, Decimal(0))
                digits = max((places(value) for value in billed_values), default=places(ordered))
                remaining = at_precision(ordered, digits) - billed
                status = ("unbilled" if not items else "matched" if remaining == 0
                          else "partially_billed" if remaining > 0 else "overbilled")
            open_items.append({"group": group, "round": key, "basis": basis,
                               "ordered": text(ordered), "linked": text(billed),
                               "remaining": text(remaining), "status": status})
    return open_items, findings


def reconcile(data):
    """Method: run every check that the supplied input makes possible."""
    if not isinstance(data, dict):
        raise ValueError("The input must be a JSON object.")
    result = {"checks": {}, "findings": [], "open_items": []}
    statement = data.get("statement")
    if statement is not None:
        summary, findings = check_lines(statement.get("lines", []))
        result["checks"]["lines"] = summary
        result["findings"] += findings
        checks, findings = check_totals(statement)
        result["checks"].update(checks)
        result["findings"] += findings
    rounds = data.get("order_rounds") or []
    if rounds:
        result["findings"] += check_cumulative(rounds)
        open_items, findings = check_links(rounds, data.get("links") or [])
        result["open_items"] = open_items
        result["findings"] += findings
    return result


def main():
    """Method: read one JSON input and print the result; errors give cause and remedy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file with statement, order_rounds and links")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        output = reconcile(data)
    except (OSError, ValueError) as error:
        cause = "The input file could not be read." if isinstance(error, OSError) else str(error)
        print(json.dumps({"error": {"type": type(error).__name__, "cause": cause,
                                    "resolution": "Fix the input JSON and run again; "
                                                  "write numbers as decimal strings."}},
                         ensure_ascii=False))
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 동작 설명: 명세서의 수량×단가, 합계, 부가세, 한글 금액을 정확한 십진수로 검산합니다.
# 발주 차수 누계와 매칭 수량을 비교해 미청구 잔량을 계산하며, 원본 값은 고치지 않습니다.
