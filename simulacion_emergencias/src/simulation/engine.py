import simpy
import numpy as np
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field

from src.models.entities import Patient, GravityLevel, StageConfig, SimulationMetrics
from src.models.analytical import JacksonNetwork
from src.config.schema import BaseParameters
from src.simulation.priority_strategy import PriorityStrategy, create_strategy
from src.simulation.patient_generator import PatientGenerator, PatientCounter


@dataclass
class StageResource:
    resource: simpy.Resource
    config: StageConfig
    busy_time: float = 0.0
    last_event_time: float = 0.0
    queue_lengths: List[float] = field(default_factory=list)
    utilization_samples: List[float] = field(default_factory=list)


class SimulationEngine:
    def __init__(
        self,
        params: BaseParameters,
        c3: int = None,
        c5: int = None,
        priority_mode: str = "fifo",
        random_seed: int = 42
    ):
        self.params = params
        self.priority_mode = priority_mode
        self.random_seed = random_seed
        
        np.random.seed(random_seed)
        
        self.env = simpy.Environment()
        
        self.stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
        
        mu = params.service_rates["mu"]
        c = params.servers["c"].copy()
        if c3 is not None:
            c[2] = c3
        if c5 is not None:
            c[4] = c5
        routing = params.routing_matrix["p"]
        
        self.stages: List[StageResource] = []
        use_priority_resource = (priority_mode == "priority")
        for i in range(5):
            config = StageConfig(
                name=self.stage_names[i],
                mu=mu[i],
                c=c[i],
                routing_probs=routing[i]
            )
            if use_priority_resource and i in [1, 2, 3, 4]:
                resource = simpy.PriorityResource(self.env, capacity=c[i])
            else:
                resource = simpy.Resource(self.env, capacity=c[i])
            self.stages.append(StageResource(resource=resource, config=config))
        
        self.strategy = create_strategy(priority_mode, priority_stages=[1, 2, 3, 4])
        
        self.metrics = SimulationMetrics()
        self.total_arrivals = 0
        self.patient_counter = PatientCounter()
        self.generator = None
        
        self._network = JacksonNetwork(
            gamma=params.external_arrivals["gamma"],
            mu=mu,
            c=c,
            routing=routing,
            stage_names=self.stage_names
        )

    def run(self, horizon_hours: float, warmup_hours: float = 0):
        self._warmup_hours = warmup_hours
        self.generator = PatientGenerator(
            self.env, self.params, self.patient_counter, self
        )
        
        if warmup_hours > 0:
            self.env.run(until=warmup_hours)
            self._reset_metrics_after_warmup()
        
        self.env.run(until=horizon_hours)
        
        return self.collect_results()

    def _reset_metrics_after_warmup(self):
        self.metrics = SimulationMetrics()
        for stage in self.stages:
            stage.busy_time = 0.0
            stage.last_event_time = self.env.now
            stage.queue_lengths.clear()
            stage.utilization_samples.clear()

    def on_arrival(self, patient: Patient):
        self.total_arrivals += 1
        self.metrics.total_arrivals += 1

    def on_patient_start(self, patient: Patient):
        pass

    def on_patient_complete(self, patient: Patient):
        self.metrics.completed_patients += 1

    def process_patient(self, patient: Patient):
        current_stage = 0
        
        while current_stage < 5:
            stage_res = self.stages[current_stage]
            config = stage_res.config
            
            patient.current_stage = current_stage
            patient.stage_entry_time = self.env.now
            
            self._record_queue_length(current_stage)
            
            request = self.strategy.request_resource(
                self.env, stage_res.resource, patient, self.metrics, current_stage
            )
            
            yield request
            
            wait_time = self.env.now - patient.stage_entry_time
            patient.wait_times.append(wait_time)
            self.metrics.record_stage_wait(current_stage, wait_time)
            
            service_time = np.random.exponential(1.0 / config.mu)
            patient.service_times.append(service_time)
            self.metrics.record_stage_service(current_stage, service_time)
            
            stage_res.busy_time += service_time
            yield self.env.timeout(service_time)
            
            self.strategy.release_resource(stage_res.resource, request)
            
            self._record_utilization(current_stage)
            
            next_stage = self._route_patient(current_stage)
            if next_stage is None:
                break
            current_stage = next_stage
        
        patient.completed = True
        patient.completion_time = self.env.now
        total_wait = sum(patient.wait_times)
        total_time = total_wait + sum(patient.service_times)
        self.metrics.record_patient_gravity(patient.gravity, total_wait, total_time)

    def _record_queue_length(self, stage: int):
        stage_res = self.stages[stage]
        queue_len = len(stage_res.resource.queue)
        stage_res.queue_lengths.append(queue_len)

    def _record_utilization(self, stage: int):
        stage_res = self.stages[stage]
        now = self.env.now
        if stage_res.last_event_time > 0:
            elapsed = now - stage_res.last_event_time
            utilization = stage_res.busy_time / (elapsed * stage_res.config.c) if elapsed > 0 else 0
            stage_res.utilization_samples.append(min(1.0, utilization))
        stage_res.last_event_time = now
        stage_res.busy_time = 0.0

    def _route_patient(self, current_stage: int) -> Optional[int]:
        probs = self.stages[current_stage].config.routing_probs
        exit_prob = self.stages[current_stage].config.exit_prob
        
        all_probs = probs + [exit_prob]
        choices = list(range(5)) + [-1]
        
        next_idx = np.random.choice(choices, p=all_probs)
        return next_idx if next_idx != -1 else None

    def collect_results(self) -> Dict:
        # Tiempo efectivo de muestreo: las metricas se registran solo despues
        # del warm-up, por lo que las tasas deben dividirse entre (T - warmup)
        # y no entre el tiempo total (evita subestimar lambda_eff y L ~10%)
        effective_time = self.env.now - getattr(self, "_warmup_hours", 0)
        stage_results = []
        for i, stage_res in enumerate(self.stages):
            waits = self.metrics.stage_wait_times[i]
            services = self.metrics.stage_service_times[i]
            queue_lens = stage_res.queue_lengths
            utils = stage_res.utilization_samples
            
            stage_results.append({
                "name": self.stage_names[i],
                "lambda_eff": len(waits) / effective_time if effective_time > 0 else 0,
                "mu": stage_res.config.mu,
                "c": stage_res.config.c,
                "rho": np.mean(utils) if utils else 0,
                "Wq": np.mean(waits) if waits else 0,
                "W": np.mean(waits) + np.mean(services) if waits and services else 0,
                "Lq": np.mean(queue_lens) if queue_lens else 0,
                "L": len(waits) / effective_time * (np.mean(waits) + np.mean(services)) if waits and services and effective_time > 0 else 0,
                "completed": len(waits),
            })
        
        gravity_results = {}
        for g in GravityLevel:
            stats = self.metrics.get_gravity_stats(g)
            gravity_results[g.name] = stats
        
        total_L = sum(r["L"] for r in stage_results)
        total_lambda = self.params.external_arrivals["gamma"][0]
        W_system = total_L / total_lambda if total_lambda > 0 else 0
        
        bottleneck_idx = max(range(5), key=lambda i: stage_results[i]["rho"])
        stage_results[bottleneck_idx]["is_bottleneck"] = True
        
        return {
            "stages": stage_results,
            "gravity": gravity_results,
            "total_L": total_L,
            "total_lambda": total_lambda,
            "W_system": W_system,
            "bottleneck_idx": bottleneck_idx,
            "sim_time": self.env.now,
            "completed_patients": self.metrics.completed_patients,
        }


def run_single_replication(
    params: BaseParameters,
    c3: int,
    c5: int,
    priority_mode: str,
    horizon_hours: float,
    warmup_hours: float,
    seed: int
) -> Dict:
    engine = SimulationEngine(
        params=params,
        c3=c3,
        c5=c5,
        priority_mode=priority_mode,
        random_seed=seed
    )
    return engine.run(horizon_hours, warmup_hours)