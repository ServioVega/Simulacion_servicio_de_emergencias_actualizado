from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

from src.models.analytical import create_base_network, AnalyticalResult, StageResult
from src.config.schema import BaseParameters
from src.simulation.engine import run_single_replication
from src.simulation.statistics import AggregatedResults, ReplicationResult, compare_analytical_vs_simulation


@dataclass
class ExperimentConfig:
    c3: int
    c5: int
    label: str


def analytical_to_dict(result: AnalyticalResult) -> Dict[str, Any]:
    stages = []
    for s in result.stages:
        stages.append({
            "name": s.name,
            "lambda_eff": s.lambda_eff,
            "mu": s.mu,
            "c": s.c,
            "rho": s.rho,
            "Wq": s.Wq,
            "W": s.W,
            "Lq": s.Lq,
            "L": s.L,
            "is_bottleneck": s.is_bottleneck,
        })
    return {
        "stages": stages,
        "total_L": result.total_L,
        "total_lambda": result.total_lambda,
        "W_system": result.W_system,
        "bottleneck_idx": result.bottleneck_idx,
        "is_stable": result.is_stable,
    }


def run_analytical_sweep(
    params: BaseParameters,
    c3_range: List[int],
    c5_range: List[int]
) -> List[Dict[str, Any]]:
    network = create_base_network(params)
    results = []
    
    for c3 in c3_range:
        for c5 in c5_range:
            result = network.analyze_with_servers(c3, c5)
            d = analytical_to_dict(result)
            d["c3"] = c3
            d["c5"] = c5
            results.append(d)
    
    return results


def run_simulation_replications(
    params: BaseParameters,
    config: ExperimentConfig,
    priority_mode: str,
    n_replications: int,
    horizon_hours: float,
    warmup_hours: float,
    base_seed: int
) -> AggregatedResults:
    replications = []
    
    for rep in range(n_replications):
        seed = base_seed + rep * 1000 + config.c3 * 100 + config.c5 * 10
        result = run_single_replication(
            params=params,
            c3=config.c3,
            c5=config.c5,
            priority_mode=priority_mode,
            horizon_hours=horizon_hours,
            warmup_hours=warmup_hours,
            seed=seed
        )
        
        replications.append(ReplicationResult(
            stages=result["stages"],
            gravity=result["gravity"],
            total_L=result["total_L"],
            W_system=result["W_system"],
            bottleneck_idx=result["bottleneck_idx"],
            completed_patients=result["completed_patients"]
        ))
    
    return AggregatedResults.from_replications(replications)


def run_validation(
    params: BaseParameters,
    config: ExperimentConfig,
    n_replications: int,
    horizon_hours: float,
    warmup_hours: float,
    base_seed: int,
    threshold: float = 0.05
) -> Dict[str, Any]:
    network = create_base_network(params)
    analytical = network.analyze_with_servers(config.c3, config.c5)
    analytical_dict = analytical_to_dict(analytical)
    
    sim_results = run_simulation_replications(
        params, config, "fifo", n_replications, horizon_hours, warmup_hours, base_seed
    )
    
    comparison = compare_analytical_vs_simulation(analytical_dict, sim_results, threshold)
    
    effective_hours = horizon_hours - warmup_hours
    return {
        "analytical": analytical_dict,
        "simulation": {
            "stage_means": sim_results.stage_means,
            "stage_ci95": sim_results.stage_ci95,
            "W_system_mean": sim_results.W_system_mean,
            "W_system_std": sim_results.W_system_std,
            "W_system_ci95": sim_results.W_system_ci95,
            "completed_patients_mean": sim_results.completed_patients_mean,
            "completed_patients_std": sim_results.completed_patients_std,
            "throughput_per_hour": (sim_results.completed_patients_mean / effective_hours
                                    if effective_hours > 0 else 0.0),
        },
        "comparison": comparison
    }


def run_priority_comparison(
    params: BaseParameters,
    config: ExperimentConfig,
    n_replications: int,
    horizon_hours: float,
    warmup_hours: float,
    base_seed: int
) -> Dict[str, Any]:
    fifo_results = run_simulation_replications(
        params, config, "fifo", n_replications, horizon_hours, warmup_hours, base_seed
    )
    
    priority_results = run_simulation_replications(
        params, config, "priority", n_replications, horizon_hours, warmup_hours, base_seed
    )
    
    gravity_comparison = {}
    for g_name in fifo_results.gravity_means.keys():
        fifo_wq = fifo_results.gravity_means[g_name]["Wq"]
        pri_wq = priority_results.gravity_means[g_name]["Wq"]
        
        gravity_comparison[g_name] = {
            "fifo_Wq": fifo_wq,
            "priority_Wq": pri_wq,
            "difference": pri_wq - fifo_wq,
            "improvement_pct": (fifo_wq - pri_wq) / fifo_wq * 100 if fifo_wq > 0 else 0
        }
    
    effective_hours = horizon_hours - warmup_hours
    return {
        "fifo": {
            "gravity_means": fifo_results.gravity_means,
            "gravity_ci95": fifo_results.gravity_ci95,
            "stage_means": fifo_results.stage_means,
            "W_system_mean": fifo_results.W_system_mean,
            "W_system_ci95": fifo_results.W_system_ci95,
            "completed_patients_mean": fifo_results.completed_patients_mean,
            "throughput_per_hour": (fifo_results.completed_patients_mean / effective_hours
                                    if effective_hours > 0 else 0.0),
        },
        "priority": {
            "gravity_means": priority_results.gravity_means,
            "gravity_ci95": priority_results.gravity_ci95,
            "stage_means": priority_results.stage_means,
            "W_system_mean": priority_results.W_system_mean,
            "W_system_ci95": priority_results.W_system_ci95,
            "completed_patients_mean": priority_results.completed_patients_mean,
            "throughput_per_hour": (priority_results.completed_patients_mean / effective_hours
                                    if effective_hours > 0 else 0.0),
        },
        "gravity_comparison": gravity_comparison
    }


def results_to_dataframe(analytical_results: List[Dict]) -> pd.DataFrame:
    rows = []
    for r in analytical_results:
        for s in r["stages"]:
            rows.append({
                "c3": r["c3"],
                "c5": r["c5"],
                "stage": s["name"],
                "lambda_eff": s["lambda_eff"],
                "rho": s["rho"],
                "Wq": s["Wq"],
                "W": s["W"],
                "Lq": s["Lq"],
                "L": s["L"],
                "is_bottleneck": s["is_bottleneck"],
            })
    return pd.DataFrame(rows)