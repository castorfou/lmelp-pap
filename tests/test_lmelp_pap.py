"""Tests du package lmelp_pap."""

import lmelp_pap as package


def test_package_importable() -> None:
    """Le package s'importe depuis src/."""
    assert package.__name__ == "lmelp_pap"
