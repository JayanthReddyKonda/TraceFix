from calc.core import Calculator, accumulate, add


def test_add():
    assert add(1, 2) == 3


def test_accumulate():
    assert accumulate([1, 2, 3]) == 6


def test_total():
    calc = Calculator()
    assert calc.total([2, 4]) == 6
