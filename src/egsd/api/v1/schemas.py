"""Pydantic DTOs mirroring the OPZ data contracts (§2.1 and Karta Modułu I)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Quantity(BaseModel):
    value: float
    unit: str


# ----- gas-engine: point-properties (OPZ §2.1) --------------------------------


class RequestMeta(BaseModel):
    requestId: str | None = None
    callerModule: str | None = None


class StateVariables(BaseModel):
    pressure: Quantity
    temperature: Quantity


class EngineConfig(BaseModel):
    preferredModel: str = "GERG-2008"
    allowScreeningFallback: bool = False


class PointPropertiesRequest(BaseModel):
    meta: RequestMeta = Field(default_factory=RequestMeta)
    gasComposition: dict[str, float]
    stateVariables: StateVariables
    config: EngineConfig = Field(default_factory=EngineConfig)


class ValidationBlock(BaseModel):
    status: str
    isWithinModelRange: bool
    warnings: list[str] = []


class PointPropertiesResponse(BaseModel):
    meta: dict
    calculatedValues: dict[str, Quantity]
    validation: ValidationBlock


# ----- gas-engine: combustion (ISO 6976) --------------------------------------


class CombustionRequest(BaseModel):
    gasComposition: dict[str, float]
    referencePair: str = "25/0"


class CombustionResponse(BaseModel):
    referencePair: str
    grossCalorificValue: Quantity
    netCalorificValue: Quantity
    relativeDensity: float
    wobbeIndex: Quantity


# ----- thermo: compression (Karta Modułu I) -----------------------------------


class CompressionRequest(BaseModel):
    compositionId: str | None = Field(
        default=None, description="Reference profile code; alternative to inline composition."
    )
    gasComposition: dict[str, float] | None = None
    massFlowRate: Quantity
    inletPressure: Quantity
    inletTemperature: Quantity
    outletPressureTarget: Quantity
    isentropicEfficiency: float = 0.78
    mechanicalEfficiency: float = 1.0


class CompressionResponse(BaseModel):
    requiredShaftPower: Quantity
    outletTemperature: Quantity
    polytropicHead: Quantity
    isentropicHead: Quantity
    validationStatus: str
    resultClass: str
    warnings: list[str] = []


# ----- hydraulics: steady flow + linepack (Karta Modułu II) --------------------


class HydraulicsRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    diameter: Quantity  # internal diameter D
    roughness: Quantity  # absolute roughness k
    length: Quantity  # segment length L
    inletPressure: Quantity
    gasTemperature: Quantity
    normalFlow: Quantity  # volumetric flow at normal conditions (Nm3/h)


class HydraulicsResponse(BaseModel):
    outletPressure: Quantity
    pressureDrop: Quantity
    massFlow: Quantity
    averageVelocity: Quantity
    reynoldsNumber: float
    frictionFactor: float
    flowRegime: str
    machNumber: float
    validationStatus: str
    resultClass: str
    warnings: list[str] = []


class LinepackResponse(BaseModel):
    linepackMass: Quantity
    linepackNormalVolume: Quantity
    averagePressure: Quantity
    averageDensity: Quantity


# ----- gas blending + quality (custom compositions, propanization) -------------


class BlendStream(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    share: float = Field(gt=0, description="Relative molar/volumetric share of this stream.")


class BlendRequest(BaseModel):
    streams: list[BlendStream]
    referencePair: str = "25/0"


class BlendResponse(BaseModel):
    composition: dict[str, float]
    grossCalorificValue: Quantity
    wobbeIndex: Quantity
    relativeDensity: float
    normalDensity: Quantity


class QualityLimitsDTO(BaseModel):
    wobbeMin: float = 45.0
    wobbeMax: float = 56.9
    grossCvMin: float = 34.0
    referencePair: str = "25/0"


class QualityRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    limits: QualityLimitsDTO | None = None
    # Explicit, versioned requirement set selected from the catalog (OPZ §21, MVP #7).
    # Takes precedence over `limits` when provided.
    requirementSetId: str | None = None


class QualityRequirementSetDTO(BaseModel):
    code: str
    name: str
    version: str
    application: str
    geography: str
    referenceDocument: str
    referencePair: str
    wobbeMin: float
    wobbeMax: float
    grossCvMin: float
    status: str
    source: str


class ConditioningProposalDTO(BaseModel):
    action: str
    additive: str
    additiveFractionMol: float
    resultingWobbe: Quantity
    resultingGrossCv: Quantity
    note: str


class QualityResponse(BaseModel):
    withinSpec: bool
    wobbeIndex: Quantity
    grossCalorificValue: Quantity
    relativeDensity: float
    violations: list[str]
    proposal: ConditioningProposalDTO | None = None
    # Which requirement set was applied (explicit provenance, §14 comparability).
    requirementSet: str = "domyślny grupa E (wbudowany)"


# ----- storage: CAES -----------------------------------------------------------


class CaesRequest(BaseModel):
    cavernVolume: Quantity
    maxPressure: Quantity
    minPressure: Quantity
    storageTemperature: Quantity | None = None
    ambientPressure: Quantity | None = None
    ambientTemperature: Quantity | None = None
    chargeIsentropicEfficiency: float = 0.80
    dischargeIsentropicEfficiency: float = 0.85
    compressionStages: int = 3
    expansionStages: int = 3
    gasComposition: dict[str, float] | None = None  # defaults to air


class CaesResponse(BaseModel):
    storedAirMassMax: Quantity
    workingAirMass: Quantity
    chargeEnergy: Quantity
    dischargeEnergy: Quantity
    roundTripEfficiency: float
    dischargeOutletTemperature: Quantity
    resultClass: str
    warnings: list[str] = []


# ----- device selection (compressor / expander technology) ---------------------


class DeviceCardDTO(BaseModel):
    code: str
    name: str
    role: str
    category: str
    stageRatioMin: float
    stageRatioMax: float
    stageRatioOptimal: float
    isentropicEfficiencyNominal: float
    massFlowMin: Quantity
    massFlowMax: Quantity
    notes: str


class AuxiliaryDTO(BaseModel):
    kind: str
    description: str
    duty: Quantity | None = None
    source: str | None = None


class DeviceCandidateDTO(BaseModel):
    code: str
    name: str
    category: str
    feasible: bool
    stages: int
    stageRatio: float
    effectiveEfficiency: float
    reason: str = ""


class DeviceSelectRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    massFlowRate: Quantity
    inletPressure: Quantity
    inletTemperature: Quantity
    outletPressureTarget: Quantity


class SelectCompressorResponse(BaseModel):
    selected: DeviceCandidateDTO | None
    requiredShaftPower: Quantity
    outletTemperature: Quantity
    pressureRatio: float
    auxiliaries: list[AuxiliaryDTO]
    alternatives: list[DeviceCandidateDTO]
    resultClass: str


class SelectExpanderResponse(BaseModel):
    selected: DeviceCandidateDTO | None
    recoveredPower: Quantity
    outletTemperatureSingleStage: Quantity
    pressureRatio: float
    auxiliaries: list[AuxiliaryDTO]
    alternatives: list[DeviceCandidateDTO]
    resultClass: str


# ----- prices (history, trend, scenarios) --------------------------------------


class PricePointDTO(BaseModel):
    date: str
    value: float


class PriceSeriesSummary(BaseModel):
    code: str
    name: str
    unit: str
    currency: str
    source: str
    current: PricePointDTO


class PriceHistoryResponse(BaseModel):
    code: str
    name: str
    unit: str
    currency: str
    source: str
    current: PricePointDTO
    points: list[PricePointDTO]


class TrendResponse(BaseModel):
    code: str
    annualizedReturn: float
    pctChangeWindow: float
    annualizedVolatility: float
    movingAverageLast: float
    movingAverageWindow: int


class ScenarioBandDTO(BaseModel):
    year: int
    low: float
    base: float
    high: float


class ScenarioResponse(BaseModel):
    seriesCode: str
    unit: str
    startValue: float
    annualizedReturn: float
    bands: list[ScenarioBandDTO]


class MacroScenarioDTO(BaseModel):
    code: str
    name: str
    family: str
    source: str
    vintage: str
    notes: str


class ReportScenarioResponse(BaseModel):
    seriesCode: str
    unit: str
    referenceValue: float
    anchored: bool
    basis: str
    sources: list[str]
    bands: list[ScenarioBandDTO]


# ----- finance (DCF) -----------------------------------------------------------


class DcfRequest(BaseModel):
    capex: float
    discountRate: float
    horizonYears: int
    opexPerYear: list[float]
    energyCostPerYear: list[float] = []
    etsCostPerYear: list[float] = []
    revenuePerYear: list[float] = []
    outputPerYear: list[float] = []
    lcoKind: str | None = None  # LCOE | LCOH | LCOHeat | LCOS


class DcfResponse(BaseModel):
    npv: float
    irr: float | None
    lcoValue: float | None
    lcoKind: str | None
    netCashFlows: list[float]
    warnings: list[str] = []


class SensitivityPointDTO(BaseModel):
    deltaPct: float
    npv: float


class SensitivityAxisDTO(BaseModel):
    parameter: str
    points: list[SensitivityPointDTO]


class TornadoResponse(BaseModel):
    baseNpv: float
    axes: list[SensitivityAxisDTO]
