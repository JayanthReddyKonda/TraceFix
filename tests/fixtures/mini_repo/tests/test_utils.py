from calc.utils import scale, sum_list


def test_sum_list():
    assert sum_list([1, 2]) == 3


def test_scale():
    assert scale([1, 2], 2) == [2, 4]
