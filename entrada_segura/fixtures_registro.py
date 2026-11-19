"""Registro de fixtures por CONJUNTO aprovado (§4.6). PLACEHOLDER substituído no commit do registro."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ConjuntoFixture:
    id: str
    base: str
    arquivos: Mapping[str, str]


CONJUNTOS: tuple[ConjuntoFixture, ...] = ()
