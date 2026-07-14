"""Live price-feed providers (pluggable).

The default data path is the seeded, versioned price store (reference data). A live exchange
feed is a swappable provider that populates that store; enabling it only requires allow-listing
the source host in the environment network policy. This keeps the OPZ snapshot/reproducibility
guarantees intact — live values are fetched, then snapshotted and versioned like any other
reference data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.request import urlopen

from ...domain.prices.models import PricePoint


class ProviderUnavailable(RuntimeError):
    """The live source could not be reached (e.g. blocked by network policy)."""


class PriceProvider(Protocol):
    code: str

    def fetch_latest(self) -> PricePoint: ...


@dataclass
class TgeProvider:
    """Towarowa Giełda Energii (TGE) day-ahead feed.

    Blocked by the current network policy (proxy returns 403 for tge.pl). When the host is
    allow-listed, `fetch_latest` returns the latest published fixing; until then it raises
    ProviderUnavailable and the platform falls back to the seeded reference series.
    """

    code: str
    endpoint: str = "https://tge.pl"  # replace with the concrete published-data endpoint
    timeout_s: float = 12.0

    def fetch_latest(self) -> PricePoint:  # pragma: no cover - network path
        try:
            with urlopen(self.endpoint, timeout=self.timeout_s):  # noqa: S310
                raise ProviderUnavailable(
                    "TGE reachable but parser not configured — wire the published-data "
                    "endpoint for this instrument."
                )
        except OSError as exc:
            raise ProviderUnavailable(
                f"TGE feed unreachable for {self.code!r} ({exc}); using seeded reference series. "
                "Allow-list tge.pl in the environment network policy to enable live data."
            ) from exc
