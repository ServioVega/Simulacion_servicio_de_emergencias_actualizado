import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any
from src.models.entities import SimulationMetrics, GravityLevel


@dataclass
class ReplicationResult:
    stages: List[Dict[str, Any]]
    gravity: Dict[str, Dict[str, Any]]
    total_L: float
    W_system: float
    bottleneck_idx: int
    completed_patients: int


@dataclass
class AggregatedResults:
    stage_means: List[Dict[str, float]]
    stage_stds: List[Dict[str, float]]
    stage_ci95: List[Dict[str, tuple]]
    gravity_means: Dict[str, Dict[str, float]]
    gravity_stds: Dict[str, Dict[str, float]]
    gravity_ci95: Dict[str, Dict[str, tuple]]
    W_system_mean: float
    W_system_std: float
    W_system_ci95: tuple
    bottleneck_distribution: Dict[int, int]
    completed_patients_mean: float = 0.0
    completed_patients_std: float = 0.0
    
    @classmethod
    def from_replications(cls, replications: List[ReplicationResult], n_stages: int = 5):
        if not replications:
            raise ValueError("No hay réplicas para agregar")
        
        stage_keys = ["lambda_eff", "rho", "Wq", "W", "Lq", "L"]
        stage_means = []
        stage_stds = []
        stage_ci95 = []
        
        for i in range(n_stages):
            stage_data = {k: [] for k in stage_keys}
            for r in replications:
                if i < len(r.stages):
                    for k in stage_keys:
                        stage_data[k].append(r.stages[i].get(k, 0))
            
            means = {}
            stds = {}
            cis = {}
            for k in stage_keys:
                vals = np.array(stage_data[k])
                if len(vals) > 0:
                    means[k] = float(np.mean(vals))
                    stds[k] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                    if len(vals) > 1:
                        se = stds[k] / np.sqrt(len(vals))
                        cis[k] = (float(means[k] - 1.96 * se), float(means[k] + 1.96 * se))
                    else:
                        cis[k] = (means[k], means[k])
                else:
                    means[k] = stds[k] = 0.0
                    cis[k] = (0.0, 0.0)
            
            stage_means.append(means)
            stage_stds.append(stds)
            stage_ci95.append(cis)
        
        gravity_levels = [g.name for g in GravityLevel]
        gravity_means = {}
        gravity_stds = {}
        gravity_ci95 = {}
        
        for g_name in gravity_levels:
            waits = []
            totals = []
            counts = []
            for r in replications:
                if g_name in r.gravity:
                    waits.append(r.gravity[g_name].get("Wq", 0))
                    totals.append(r.gravity[g_name].get("W", 0))
                    counts.append(r.gravity[g_name].get("count", 0))
            
            if waits:
                gravity_means[g_name] = {
                    "Wq": float(np.mean(waits)),
                    "W": float(np.mean(totals)),
                    "count": float(np.mean(counts))
                }
                gravity_stds[g_name] = {
                    "Wq": float(np.std(waits, ddof=1)) if len(waits) > 1 else 0.0,
                    "W": float(np.std(totals, ddof=1)) if len(totals) > 1 else 0.0,
                }
                if len(waits) > 1:
                    se_wq = gravity_stds[g_name]["Wq"] / np.sqrt(len(waits))
                    se_w = gravity_stds[g_name]["W"] / np.sqrt(len(totals))
                    gravity_ci95[g_name] = {
                        "Wq": (float(np.mean(waits) - 1.96 * se_wq), float(np.mean(waits) + 1.96 * se_wq)),
                        "W": (float(np.mean(totals) - 1.96 * se_w), float(np.mean(totals) + 1.96 * se_w)),
                    }
                else:
                    gravity_ci95[g_name] = {
                        "Wq": (gravity_means[g_name]["Wq"], gravity_means[g_name]["Wq"]),
                        "W": (gravity_means[g_name]["W"], gravity_means[g_name]["W"]),
                    }
            else:
                gravity_means[g_name] = {"Wq": 0, "W": 0, "count": 0}
                gravity_stds[g_name] = {"Wq": 0, "W": 0}
                gravity_ci95[g_name] = {"Wq": (0, 0), "W": (0, 0)}
        
        W_vals = [r.W_system for r in replications]
        W_mean = float(np.mean(W_vals))
        W_std = float(np.std(W_vals, ddof=1)) if len(W_vals) > 1 else 0.0
        if len(W_vals) > 1:
            se = W_std / np.sqrt(len(W_vals))
            W_ci = (float(W_mean - 1.96 * se), float(W_mean + 1.96 * se))
        else:
            W_ci = (W_mean, W_mean)
        
        bottleneck_dist = {}
        for r in replications:
            idx = r.bottleneck_idx
            bottleneck_dist[idx] = bottleneck_dist.get(idx, 0) + 1
        
        # Pacientes completados por replicacion (throughput)
        completed_vals = [r.completed_patients for r in replications]
        completed_mean = float(np.mean(completed_vals)) if completed_vals else 0.0
        completed_std = float(np.std(completed_vals, ddof=1)) if len(completed_vals) > 1 else 0.0
        
        return cls(
            stage_means=stage_means,
            stage_stds=stage_stds,
            stage_ci95=stage_ci95,
            gravity_means=gravity_means,
            gravity_stds=gravity_stds,
            gravity_ci95=gravity_ci95,
            W_system_mean=W_mean,
            W_system_std=W_std,
            W_system_ci95=W_ci,
            bottleneck_distribution=bottleneck_dist,
            completed_patients_mean=completed_mean,
            completed_patients_std=completed_std
        )


def compare_analytical_vs_simulation(
    analytical: Dict[str, Any],
    simulation: AggregatedResults,
    threshold: float = 0.05,
    abs_tol_min: float = 0.05
) -> Dict[str, Any]:
    """Compara Wq analitico vs simulado etapa por etapa.
    
    Criterio de validacion (practica estandar, Law & Kelton):
      1) Diferencia relativa <= threshold (por defecto 5%), O
         diferencia absoluta <= abs_tol_min (minutos), lo que evita falsos
         negativos en etapas con Wq casi nulo (la diferencia relativa se
         dispara aunque la diferencia sea de milisegundos).
      2) El valor analitico cae dentro del IC95 de la simulacion (con la
         misma tolerancia absoluta, pues el IC con 30 replicas tambien
         tiene error de Monte Carlo).
    """
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    abs_tol = abs_tol_min / 60.0  # horas
    comparison = {}
    all_pass = True
    
    for i, name in enumerate(stage_names):
        an_Wq = analytical["stages"][i]["Wq"]
        sim_Wq = simulation.stage_means[i]["Wq"]
        sim_ci = simulation.stage_ci95[i]["Wq"]
        
        abs_diff = abs(an_Wq - sim_Wq)
        
        if an_Wq == 0 and sim_Wq == 0:
            diff_pct = 0.0
        elif an_Wq == 0:
            diff_pct = float('inf')
        else:
            diff_pct = abs_diff / an_Wq
        
        diff_ok = (diff_pct <= threshold) or (abs_diff <= abs_tol)
        in_ci = (sim_ci[0] - abs_tol) <= an_Wq <= (sim_ci[1] + abs_tol)
        passed = diff_ok and in_ci
        
        comparison[name] = {
            "analytical_Wq": an_Wq,
            "simulation_Wq_mean": sim_Wq,
            "simulation_Wq_ci95": sim_ci,
            "diff_pct": diff_pct,
            "abs_diff_min": abs_diff * 60.0,
            "in_ci": in_ci,
            "diff_ok": diff_ok,
            "passed": passed
        }
        
        if not passed:
            all_pass = False
    
    comparison["overall_passed"] = all_pass
    comparison["abs_tol_min"] = abs_tol_min
    return comparison