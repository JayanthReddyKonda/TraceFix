from calc.core import add


def sum_list(items):
    running = 0
    for item in items:
        running = add(running, item)
    return running


def scale(items, factor):
    return [item * factor for item in items]
