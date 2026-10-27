from typing import List, Dict, Any
from dataclasses import dataclass
from src.config.schema import BaseParameters, ParameterSweepConfig
from src.experiments.runner import (
    run_analytical_sweep,
    run_simulation_replications,
    run_validation,
    run_priority_comparison,
    ExperimentConfig,
    results_to_dataframe,
    analytical_to_dict
)
from src.models.analytical import create_base_network, AnalyticalResult


@dataclass
class SweepResult:
    analytical_results: List[Dict[str, Any]]
    validation_results: Dict[str, Any]
    priority_results: Dict[str, Any]
    analytical_df: Any


def run_full_experiment(params: BaseParameters) -> SweepResult:
    sweep_config = params.parameter_sweep
    sim_config = params.simulation
    
    print("=== Barrido analítico (c3 x c5) ===")
    analytical_results = run_analytical_sweep(
        params,
        sweep_config.doctors_range,
        sweep_config.nurses_range
    )
    print(f"Completado: {len(analytical_results)} combinaciones")
    
    analytical_df = results_to_dataframe(analytical_results)
    
    validation_results = {}
    priority_results = {}
    
    if sweep_config.selected_scenarios:
        print("\n=== Validación y comparación prioridad (escenarios seleccionados) ===")
        for scen in sweep_config.selected_scenarios:
            config = ExperimentConfig(c3=scen["c3"], c5=scen["c5"], label=scen["label"])
            print(f"\nEscenario: {config.label} (c3={config.c3}, c5={config.c5})")
            
            val = run_validation(
                params=params,
                config=config,
                n_replications=sim_config.replications,
                horizon_hours=sim_config.horizon_hours,
                warmup_hours=sim_config.warmup_hours,
                base_seed=sim_config.random_seed,
                threshold=sim_config.validation_threshold
            )
            validation_results[config.label] = val
            
            passed = val["comparison"]["overall_passed"]
            print(f"  Validación analítico vs simulación: {'PASÓ' if passed else 'FALLÓ'}")
            
            pri = run_priority_comparison(
                params=params,
                config=config,
                n_replications=sim_config.replications,
                horizon_hours=sim_config.horizon_hours,
                warmup_hours=sim_config.warmup_hours,
                base_seed=sim_config.random_seed
            )
            priority_results[config.label] = pri
            
            print(f"  Comparación prioridad completada")
    
    return SweepResult(
        analytical_results=analytical_results,
        validation_results=validation_results,
        priority_results=priority_results,
        analytical_df=analytical_df
    )


def find_min_stable_staffing(analytical_results: List[Dict], max_W_system: float = 120) -> Dict[str, Any]:
    stable = [r for r in analytical_results if r["is_stable"]]
    if not stable:
        return {"found": False, "message": "No hay configuraciones estables"}
    
    candidates = [r for r in stable if r["W_system"] * 60 <= max_W_system]
    if not candidates:
        return {"found": False, "message": f"Ninguna configuración estable tiene W < {max_W_system} min"}
    
    best = min(candidates, key=lambda r: r["c3"] + r["c5"])
    return {
        "found": True,
        "c3": best["c3"],
        "c5": best["c5"],
        "W_system_min": best["W_system"] * 60,
        "bottleneck": best["stages"][best["bottleneck_idx"]]["name"] if best["bottleneck_idx"] >= 0 else "N/A"
    }