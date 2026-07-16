"""API tests: combustion emissions, merit order, and five-class expander comparison."""

from __future__ import annotations

# ----- Combustion (§27, EMI-CMB) ----------------------------------------------


def test_combustion_emissions_from_composition(client):
    r = client.post(
        "/api/v1/combustion/emissions",
        json={
            "gasComposition": {"methane": 0.95, "ethane": 0.03, "propane": 0.02},
            "options": {"usefulEfficiency": 0.9, "flueO2DryPct": 3.0},
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["method"] == "stoichiometric"
    assert d["excessAirRatio"] > 1.0
    assert d["co2KgPerGjInput"] > 0
    assert d["co2KgPerGjUseful"] > d["co2KgPerGjInput"]
    assert "carbon_dioxide" in d["flueGasDry"]


def test_combustion_compare_before_after_propane(client):
    r = client.post(
        "/api/v1/combustion/compare",
        json={
            "baseGasComposition": {"methane": 1.0},
            "modifiedGasComposition": {"methane": 0.9, "propane": 0.1},
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    # Propane enrichment raises CO2 per Nm3 of fuel.
    assert d["deltaCo2KgPerNm3Fuel"] > 0
    assert d["modified"]["co2TotalMolPerMol"] > d["base"]["co2TotalMolPerMol"]


def test_combustion_rejects_unknown_component(client):
    r = client.post(
        "/api/v1/combustion/emissions", json={"gasComposition": {"unobtainium": 1.0}}
    )
    assert r.status_code == 422


# ----- Merit order (§29, BEN-MER) ---------------------------------------------


def test_merit_order_heat_ranks_and_decomposes(client):
    r = client.post(
        "/api/v1/merit-order",
        json={
            "product": "heat",
            "technologies": [
                {"techId": "BOIL", "name": "Kocioł gazowy", "functionalUnit": "GJ_th",
                 "efficiency": 0.92, "fuelPricePerMwh": 120, "emissionFactorTPerMwhFuel": 0.202,
                 "co2PricePerT": 350, "variableOpexPerMwh": 2, "dataQuality": "literature"},
                {"techId": "HP", "name": "Pompa ciepła", "functionalUnit": "GJ_th",
                 "efficiency": 1.0, "auxEnergyRatio": 0.33, "auxPricePerMwh": 450,
                 "variableOpexPerMwh": 3, "dataQuality": "family"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["functionalUnit"] == "GJ_th"
    assert d["ranking"][0]["rank"] == 1
    top = d["ranking"][0]
    assert top["decomposition"]["total"] == top["marginalCost"]
    assert d["metadata"]["configChecksum"].startswith("sha256:")


def test_merit_order_gatekeeper_blocks_incomparable(client):
    r = client.post(
        "/api/v1/merit-order",
        json={
            "product": "electricity",
            "technologies": [
                {"techId": "A", "name": "A", "functionalUnit": "MWh_e", "efficiency": 0.5,
                 "variableOpexPerMwh": 10},
                {"techId": "B", "name": "B", "functionalUnit": "GJ_e", "efficiency": 0.5,
                 "variableOpexPerMwh": 10},
            ],
        },
    )
    assert r.status_code == 409, r.text
    assert "jednostk" in r.json()["detail"].lower()


def test_merit_order_unknown_product(client):
    r = client.post("/api/v1/merit-order", json={"product": "plasma", "technologies": []})
    assert r.status_code == 422


# ----- Five-class expander comparison (§25, EXP-CMP) --------------------------


def _expander_body(with_costs: bool = False) -> dict:
    body = {
        "gasComposition": {"methane": 0.96, "ethane": 0.03, "nitrogen": 0.01},
        "inletPressure": {"value": 5.0, "unit": "MPa"},
        "outletPressureTarget": {"value": 1.0, "unit": "MPa"},
        "inletTemperature": {"value": 320.0, "unit": "K"},
        "massFlowRate": {"value": 20.0, "unit": "kg/s"},
    }
    if with_costs:
        body["costModel"] = {
            "specificCapexPlnPerKw": 4000, "fixedOpexPctPerYear": 0.03,
            "electricityPricePlnPerMwh": 450, "discountRate": 0.08,
            "horizonYears": 15, "operatingHoursPerYear": 8000,
        }
    return body


def test_expander_comparison_covers_five_classes(client):
    r = client.post("/api/v1/devices/compare-expanders", json=_expander_body())
    assert r.status_code == 200, r.text
    d = r.json()
    # All five expansion technology classes must appear (§25 five cards).
    assert len(d["rows"]) == 5
    categories = {row["category"] for row in d["rows"]}
    assert categories == {
        "TurboExpander", "PistonExpander", "ScrewExpander",
        "ScrollExpander", "RootsExpander",
    }
    feasible = [row for row in d["rows"] if row["feasible"]]
    assert feasible, "at least one class should be feasible at this duty"
    top = feasible[0]
    assert top["recoveredPowerKw"] > 0
    assert top["dataQuality"] == "family"


def test_expander_comparison_with_economics(client):
    r = client.post("/api/v1/devices/compare-expanders", json=_expander_body(with_costs=True))
    assert r.status_code == 200, r.text
    top = next(row for row in r.json()["rows"] if row["feasible"])
    assert top["capexPln"] > 0
    assert top["annualEnergyMwh"] > 0
    assert top["lcoePlnPerMwh"] is not None
    assert top["annualPreheatCo2T"] is not None


def test_expander_comparison_rejects_compression_duty(client):
    body = _expander_body()
    body["outletPressureTarget"] = {"value": 8.0, "unit": "MPa"}  # above inlet -> not expansion
    r = client.post("/api/v1/devices/compare-expanders", json=body)
    assert r.status_code == 422
