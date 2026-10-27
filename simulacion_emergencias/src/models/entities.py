from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional
import numpy as np


class GravityLevel(IntEnum):
    CRITICAL = 1
    URGENT = 2
    MODERATE = 3
    MILD = 4
    NON_URGENT = 5


@dataclass
class Patient:
    id: int
    gravity: GravityLevel
    arrival_time: float
    current_stage: int = 0
    stage_entry_time: float = 0.0
    wait_times: List[float] = field(default_factory=list)
    service_times: List[float] = field(default_factory=list)
    completed: bool = False
    completion_time: float = 0.0

    @property
    def total_wait(self) -> float:
        return sum(self.wait_times)

    @property
    def total_service(self) -> float:
        return sum(self.service_times)

    @property
    def total_time(self) -> float:
        return self.total_wait + self.total_service


@dataclass
class StageConfig:
    name: str
    mu: float
    c: int
    routing_probs: List[float]

    @property
    def exit_prob(self) -> float:
        return 1.0 - sum(self.routing_probs)


@dataclass
class SimulationMetrics:
    stage_wait_times: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    stage_service_times: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    stage_queue_lengths: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    stage_utilization: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    patient_wait_by_gravity: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    patient_total_time_by_gravity: List[List[float]] = field(default_factory=lambda: [[] for _ in range(5)])
    completed_patients: int = 0
    total_arrivals: int = 0

    def record_stage_wait(self, stage: int, wait: float):
        self.stage_wait_times[stage].append(wait)

    def record_stage_service(self, stage: int, service: float):
        self.stage_service_times[stage].append(service)

    def record_patient_gravity(self, gravity: GravityLevel, wait: float, total_time: float):
        idx = gravity - 1
        self.patient_wait_by_gravity[idx].append(wait)
        self.patient_total_time_by_gravity[idx].append(total_time)

    def get_stage_stats(self, stage: int) -> dict:
        waits = self.stage_wait_times[stage]
        services = self.stage_service_times[stage]
        if not waits:
            return {"Wq": 0, "W": 0, "Lq": 0, "L": 0, "rho": 0}
        return {
            "Wq": np.mean(waits),
            "W": np.mean(waits) + np.mean(services) if services else np.mean(waits),
            "Lq": np.mean(self.stage_queue_lengths[stage]) if self.stage_queue_lengths[stage] else 0,
            "rho": np.mean(self.stage_utilization[stage]) if self.stage_utilization[stage] else 0,
        }

    def get_gravity_stats(self, gravity: GravityLevel) -> dict:
        idx = gravity - 1
        waits = self.patient_wait_by_gravity[idx]
        totals = self.patient_total_time_by_gravity[idx]
        if not waits:
            return {"Wq": 0, "W": 0}
        return {
            "Wq": np.mean(waits),
            "W": np.mean(totals),
            "count": len(waits)
        }