from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any
import yaml
from pathlib import Path


class GravityConfig(BaseModel):
    distribution: List[float] = Field(..., min_length=5, max_length=5)
    labels: List[str] = Field(..., min_length=5, max_length=5)

    @field_validator("distribution")
    @classmethod
    def validate_distribution(cls, v):
        if abs(sum(v) - 1.0) > 1e-6:
            raise ValueError("Distribución de gravedad debe sumar 1.0")
        if any(x < 0 for x in v):
            raise ValueError("Porcentajes de gravedad deben ser ≥ 0")
        return v


class SimulationConfig(BaseModel):
    replications: int = Field(..., gt=0)
    horizon_hours: float = Field(..., gt=0)
    warmup_hours: float = Field(..., ge=0)
    random_seed: int = Field(..., ge=0)
    validation_threshold: float = Field(..., gt=0, lt=1)


class ParameterSweepConfig(BaseModel):
    doctors_range: List[int] = Field(..., min_length=1)
    nurses_range: List[int] = Field(..., min_length=1)
    selected_scenarios: List[Dict[str, Any]] = Field(default_factory=list)


class BaseParameters(BaseModel):
    external_arrivals: Dict[str, List[float]]
    service_rates: Dict[str, List[float]]
    servers: Dict[str, List[int]]
    routing_matrix: Dict[str, List[List[float]]]
    gravity_levels: GravityConfig
    simulation: SimulationConfig
    parameter_sweep: ParameterSweepConfig

    @field_validator("external_arrivals", "service_rates", "servers")
    @classmethod
    def validate_length_5(cls, v):
        key = list(v.keys())[0]
        if len(v[key]) != 5:
            raise ValueError(f"{key} debe tener 5 elementos (5 etapas)")
        return v

    @field_validator("routing_matrix")
    @classmethod
    def validate_routing(cls, v):
        p = v["p"]
        if len(p) != 5 or any(len(row) != 5 for row in p):
            raise ValueError("Matriz de enrutamiento debe ser 5x5")
        for i, row in enumerate(p):
            if sum(row) > 1.0 + 1e-6:
                raise ValueError(f"Fila {i} de matriz de enrutamiento suma > 1")
            if any(x < 0 for x in row):
                raise ValueError(f"Fila {i} tiene probabilidades negativas")
        return v


def load_parameters(config_path: str = "config/base_parameters.yaml") -> BaseParameters:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BaseParameters(**data)