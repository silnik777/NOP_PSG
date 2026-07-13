"""Memoization for point-property calls (mitigates R-01 — engine performance/contention).

Keyed by (composition, p, T) rounded to a stable resolution. This is the seam where the
Chebyshev interpolation tables mentioned in the OPZ would later plug in.
"""

from __future__ import annotations

from collections import OrderedDict

from ...domain.gas.composition import GasComposition
from ...domain.gas.properties import PointPropertiesResult
from .coolprop_engine import CoolPropGasEngine

_P_RESOLUTION = 6  # decimal places on MPa
_T_RESOLUTION = 4  # decimal places on K


class CachingGasEngine:
    """Decorates a CoolPropGasEngine with an LRU cache for point properties."""

    def __init__(self, engine: CoolPropGasEngine | None = None, max_entries: int = 4096) -> None:
        self._engine = engine or CoolPropGasEngine()
        self._max = max_entries
        self._cache: OrderedDict[tuple, PointPropertiesResult] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    @property
    def model_key(self) -> str:
        return self._engine.model_key

    @property
    def inner(self) -> CoolPropGasEngine:
        return self._engine

    def point_properties(
        self, composition: GasComposition, pressure_mpa: float, temperature_k: float
    ) -> PointPropertiesResult:
        key = (
            composition.cache_key(),
            round(pressure_mpa, _P_RESOLUTION),
            round(temperature_k, _T_RESOLUTION),
        )
        cached = self._cache.get(key)
        if cached is not None:
            self.hits += 1
            self._cache.move_to_end(key)
            return cached

        self.misses += 1
        result = self._engine.point_properties(composition, pressure_mpa, temperature_k)
        self._cache[key] = result
        self._cache.move_to_end(key)
        if len(self._cache) > self._max:
            self._cache.popitem(last=False)
        return result
