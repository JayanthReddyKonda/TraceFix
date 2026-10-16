import os


def add(a, b):
    return a + b


def multiply(a, b):
    return a * b


def accumulate(values):
    total = 0
    for value in values:
        total = add(total, value)
    return total


class Calculator:
    def total(self, values):
        return accumulate(values)

    def double(self, x):
        return multiply(x, 2)


def env_name():
    return os.environ.get("NAME", "default")
