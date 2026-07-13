"""Engine-level exceptions."""

from __future__ import annotations


class EngineError(Exception):
    """Base class for gas-engine failures."""


class OutOfRangeError(EngineError):
    """W3.4 — (p, T) outside the hard model cutoff; must be logged with a critical flag."""

    def __init__(self, message: str, *, critical: bool = True) -> None:
        super().__init__(message)
        self.critical = critical


class StateSolveError(EngineError):
    """Numerical failure while resolving a thermodynamic state."""
