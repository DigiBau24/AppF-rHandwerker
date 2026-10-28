"""Reine Geschäftslogik der Nachkalkulation.

Warum eine eigene, DB-freie Funktion? Sie ist deterministisch und lässt sich
mit simplen Unit-Tests absichern - die Ampel-Schwellen sind das Herzstück
des Produkts und sollen nie durch Infrastruktur-Code verdeckt werden.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

CENT = Decimal("0.01")
YELLOW_FROM_PERCENT = Decimal("80")   # Gelb ab 80 % Budgetverbrauch
RED_FROM_PERCENT = Decimal("100")     # Rot ab 100 %

Ampel = Literal["green", "yellow", "red"]


@dataclass(frozen=True, slots=True)
class CostSummary:
    budget_netto: Decimal
    material_kosten: Decimal
    lohnkosten: Decimal
    gesamtkosten: Decimal
    restbudget: Decimal
    budget_verbrauch_prozent: Decimal | None
    status_ampel: Ampel


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _ampel(budget: Decimal, gesamt: Decimal) -> Ampel:
    # Vergleiche ohne Division und auf ungerundeten Werten -> keine
    # Rundungsartefakte an den Schwellen (z. B. 99,999 % wird nicht zu 100 %).
    if budget <= 0:
        return "red" if gesamt > 0 else "green"
    if gesamt * 100 >= budget * RED_FROM_PERCENT:
        return "red"
    if gesamt * 100 >= budget * YELLOW_FROM_PERCENT:
        return "yellow"
    return "green"


def calculate_cost_summary(
    budget_netto: Decimal, material_kosten: Decimal, lohnkosten: Decimal
) -> CostSummary:
    """Formel: Restbudget = Budget - Material - Lohn (Lohn = Σ Stunden * Stundensatz)."""
    gesamt = material_kosten + lohnkosten
    prozent = _cents(gesamt * 100 / budget_netto) if budget_netto > 0 else None

    return CostSummary(
        budget_netto=_cents(budget_netto),
        material_kosten=_cents(material_kosten),
        # Erst Summe der Produkte, dann EINMAL runden (nicht pro Zeile)
        lohnkosten=_cents(lohnkosten),
        gesamtkosten=_cents(gesamt),
        restbudget=_cents(budget_netto - gesamt),
        budget_verbrauch_prozent=prozent,
        status_ampel=_ampel(budget_netto, gesamt),
    )
