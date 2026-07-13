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
