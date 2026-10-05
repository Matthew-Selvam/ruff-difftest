"""Test package for ruff_difftest.

Having __init__.py makes `tests` a regular package, so `from tests.fake_ruff
import ...` in the test modules resolves to THIS directory even when the
importing environment's PYTHONPATH carries an unrelated `tests` package
(regular packages beat namespace portions regardless of path order).
"""
