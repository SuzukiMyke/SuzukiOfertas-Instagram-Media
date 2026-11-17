"""Datas ISO-8601 UTC estritas e relógio injetável."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable

Relogio = Callable[[], datetime]

_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d{1,6})?(Z|\+00:00)$")


def parse_data(valor) -> datetime | None:
    """Converte 'AAAA-MM-DDTHH:MM:SS[.ffffff]Z' (ou +00:00) em datetime UTC; ``None`` se inválida."""
    if not isinstance(valor, str):
        return None
    m = _RE.match(valor)
    if not m:
        return None
    ano, mes, dia, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    frac = m.group(7)
    micro = int(frac[1:].ljust(6, "0")) if frac else 0
    try:
        return datetime(ano, mes, dia, h, mi, s, micro, tzinfo=timezone.utc)
    except ValueError:
        return None


def formatar(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def relogio_fixo(valor: str) -> Relogio:
    dt = parse_data(valor)
    if dt is None:
        raise ValueError("data de relógio inválida (use AAAA-MM-DDTHH:MM:SSZ)")
    return lambda: dt


def relogio_sistema() -> datetime:
    return datetime.now(timezone.utc)


def horas(n: float) -> timedelta:
    return timedelta(hours=n)
