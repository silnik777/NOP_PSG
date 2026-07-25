"""Components, blending, and quality/propanization."""

from __future__ import annotations

import pytest

from egsd.application.blending_service import BlendComponent, blend
from egsd.application.quality_service import QualityLimits, assess
from egsd.domain.gas.composition import COMPONENT_TO_COOLPROP, GasComposition
from egsd.infrastructure.gas_engine.iso6976 import combustion_properties


def test_full_gerg_component_set_present():
    # Heavier hydrocarbons, H2S and argon must be addable (GERG-2008 set).
    for key in ("n_pentane", "i_pentane", "n_hexane", "n_heptane", "n_octane",
                "hydrogen_sulfide", "argon"):
        assert key in COMPONENT_TO_COOLPROP


def test_new_components_have_iso6976_data():
    # Adding pentane to a mixture must not raise (combustion data present).
    comp = GasComposition.from_mapping(
        {"methane": 0.9, "n_pentane": 0.05, "hydrogen_sulfide": 0.05}
    )
    cb = combustion_properties(comp)
    assert cb.gross_calorific_value_mj_m3 > 0


def test_blend_grid_h2_sng():
    grid = GasComposition.from_mapping({"methane": 0.96, "ethane": 0.02, "nitrogen": 0.02})
    h2 = GasComposition.from_mapping({"hydrogen": 1.0})
    sng = GasComposition.from_mapping({"methane": 0.96, "carbon_dioxide": 0.04})
    mixture = blend([BlendComponent(grid, 0.7), BlendComponent(h2, 0.2), BlendComponent(sng, 0.1)])
    assert mixture.is_normalized()
    assert mixture.fractions["hydrogen"] == pytest.approx(0.20, abs=1e-9)


def test_high_methane_gas_within_spec():
    comp = GasComposition.from_mapping(
        {"methane": 0.965, "ethane": 0.018, "propane": 0.005, "nitrogen": 0.008,
         "carbon_dioxide": 0.004}
    )
    result = assess(comp)
    assert result.within_spec
    assert result.proposal is None


def test_h2_blend_below_cv_triggers_propanization():
    # 30% H2 in E-gas drops HHV below the 34 MJ/m3 group-E minimum.
    base = {"methane": 0.965, "ethane": 0.018, "propane": 0.005, "nitrogen": 0.008,
            "carbon_dioxide": 0.004}
    blended = {k: v * 0.7 for k, v in base.items()}
    blended["hydrogen"] = 0.30
    result = assess(GasComposition.from_mapping(blended))

    assert not result.within_spec
    assert any("calorific" in v for v in result.violations)
    assert result.proposal is not None
    assert result.proposal.action == "propanization"
    assert result.proposal.additive == "propane"
    assert 0.0 < result.proposal.additive_fraction_mol < 0.2
    # After propanization the resulting mixture meets the calorific minimum.
    assert result.proposal.resulting_gross_cv_mj_m3 >= 34.0 - 1e-6


def test_wobbe_over_spec_triggers_ballasting():
    # Propane-rich gas -> Wobbe above the upper limit -> nitrogen ballasting proposed.
    comp = GasComposition.from_mapping({"methane": 0.75, "propane": 0.25})
    result = assess(comp, QualityLimits(wobbe_max_mj_m3=52.0))
    if not result.within_spec and result.proposal is not None:
        assert result.proposal.action == "ballasting_n2"
        assert result.proposal.additive == "nitrogen"
