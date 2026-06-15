"""Общая настройка для pytest: путь к проекту + фикстуры."""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def log():
    lg = logging.getLogger("autoloot.test")
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    return lg
