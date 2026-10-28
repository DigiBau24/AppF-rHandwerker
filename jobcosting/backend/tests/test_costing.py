from decimal import Decimal as D

import pytest

from app.services.costing import calculate_cost_summary as calc


@pytest.mark.parametrize(
    "budget, material, lohn, ampel",
    [
        ("1000", "0", "0", "green"),
        ("1000", "500", "299.99", "green"),    # 79,999 % -> noch grün
        ("1000", "500", "300", "yellow"),      # genau 80 %
        ("1000", "900", "99.99", "yellow"),    # 99,999 % -> noch gelb
        ("1000", "900", "100", "red"),         # genau 100 %
        ("1000", "2000", "0", "red"),
        ("0", "0", "0", "green"),              # Budget 0, nichts verbraucht
        ("0", "5", "0", "red"),                # Budget 0, Kosten vorhanden
    ],
)
def test_ampel_thresholds(budget, material, lohn, ampel):
    assert calc(D(budget), D(material), D(lohn)).status_ampel == ampel


def test_restbudget_formula():
    s = calc(D("18500"), D("7420"), D("5980.50"))
    assert s.gesamtkosten == D("13400.50")
    assert s.restbudget == D("5099.50")
    assert s.budget_verbrauch_prozent == D("72.44")


def test_overrun_is_negative_rest():
    assert calc(D("9800"), D("6940"), D("3215")).restbudget == D("-355.00")


def test_lohn_is_rounded_once_not_per_row():
    # 3 Buchungen à 0,333 h * 10,00 EUR = 9,99 -> Summe wird einmal gerundet
    s = calc(D("100"), D("0"), D("3.33") * 3)
    assert s.lohnkosten == D("9.99")
