"""
@file test_audit_sensitive.py
@brief Тесты sensitive-детектора (Luhn для карт, СНИЛС-формат).
"""
from __future__ import annotations

import pytest


# Импортируем то, что есть; если каких-то функций нет — тесты пропускаем.
luhn = pytest.importorskip("case3.audit.sensitive", reason="sensitive не найден")
from case3.audit.sensitive import luhn_valid, snils_valid


class TestLuhn:
    @pytest.mark.parametrize("card", [
        "4242424242424242",  # тестовая Visa
        "5555555555554444",  # тестовая Mastercard
        "378282246310005",   # тестовая AmEx
    ])
    def test_valid_card_numbers(self, card):
        assert luhn_valid(card) is True

    @pytest.mark.parametrize("card", [
        "4242424242424241",  # последняя цифра поменяна — невалидно
        "0000000000000001",
        "1111111111111111",
        "",
        "abc",
        "12345",             # слишком короткое
    ])
    def test_invalid_card_numbers(self, card):
        assert luhn_valid(card) is False


class TestSnils:
    def test_valid_snils_format(self):
        # Валидный СНИЛС с правильной контрольной суммой.
        # 112-233-445 95 — контрольная сумма 1*9+1*8+2*7+2*6+3*5+3*4+4*3+4*2+5*1 = 95
        assert snils_valid("112-233-445 95") is True

    def test_snils_wrong_checksum(self):
        assert snils_valid("123-456-789 00") is False

    @pytest.mark.parametrize("s", [
        "",
        "abc",
        "123-456-789",       # без контрольной суммы
        "1234567890",        # без разделителей и неправильная длина
    ])
    def test_invalid_format(self, s):
        assert snils_valid(s) is False
