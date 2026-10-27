import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
import os

# Colores consistentes para escenarios y modos
COLOR_ANALITICO = '#4C72B0'
COLOR_SIMULACION = '#DD8452'
COLORES_ESCENARIO = ['#4C72B0', '#55A868', '#C44E52', '#8172B3', '#CCB974']
COLOR_FIFO = 'lightcoral'
COLOR_PRIORIDAD = 'mediumseagreen'


def plot_utilization_by_stage(
    analytical_results: List[Dict],
    selected_c3: int,
    selected_c5: int,
    save_path: Optional[str] = None
):
    target = None
    for r in analytical_results:
        if r["c3"] == selected_c3 and r["c5"] == selected_c5:
            target = r
            break
    
    if target is None:
        print(f"No se encontró resultado para c3={selected_c3}, c5={selected_c5}")
        return
    
    stages = [s["name"] for s in target["stages"]]
    rhos = [s["rho"] for s in target["stages"]]
    colors = ['red' if s["is_bottleneck"] else 'steelblue' for s in target["stages"]]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(stages, rhos, color=colors, edgecolor='black', alpha=0.8)
    ax.axhline(y=1.0, color='red', linestyle='--', linewidth=1, label='Límite estabilidad (ρ=1)')
    ax.axhline(y=0.85, color='orange', linestyle=':', linewidth=1, label='Umbral recomendado (ρ=0.85)')
    
    for bar, rho in zip(bars, rhos):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{rho:.3f}', ha='center', va='bottom', fontweight='bold')
    
    ax.set_ylabel('Utilización (ρ)', fontsize=12)
    ax.set_title(f'Utilizacion por etapa - c3={selected_c3} medicos, c5={selected_c5} enfermeros', fontsize=14)
    ax.set_ylim(0, max(1.1, max(rhos) * 1.2))
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_wait_vs_doctors(
    analytical_results: List[Dict],
    fixed_c5: int,
    save_path: Optional[str] = None
):
    filtered = [r for r in analytical_results if r["c5"] == fixed_c5 and r["is_stable"]]
    if not filtered:
        print(f"No hay resultados estables para c5={fixed_c5}")
        return
    
    filtered.sort(key=lambda x: x["c3"])
    c3_vals = [r["c3"] for r in filtered]
    
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    stage_indices = {name: i for i, name in enumerate(stage_names)}
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()
    
    for idx, stage_name in enumerate(stage_names):
        ax = axes[idx]
        Wq_vals = [r["stages"][stage_indices[stage_name]]["Wq"] * 60 for r in filtered]
        
        ax.plot(c3_vals, Wq_vals, 'o-', linewidth=2, markersize=8, color='steelblue')
        ax.set_xlabel('Medicos (c3)', fontsize=11)
        ax.set_ylabel('Espera en cola Wq (min)', fontsize=11)
        ax.set_title(f'{stage_name}', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        for x, y in zip(c3_vals, Wq_vals):
            ax.annotate(f'{y:.1f}', (x, y), textcoords="offset points", 
                       xytext=(0, 5), ha='center', fontsize=9)
    
    axes[5].axis('off')
    
    fig.suptitle(f'Espera en cola por etapa vs. Numero de medicos (c5={fixed_c5} enfermeros fijos)', fontsize=14)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_wait_by_gravity(
    priority_results: Dict[str, Any],
    scenario_label: str,
    save_path: Optional[str] = None
):
    gravity_order = ["CRITICAL", "URGENT", "MODERATE", "MILD", "NON_URGENT"]
    gravity_labels = ["Crítico (1)", "Urgente (2)", "Moderado (3)", "Leve (4)", "No urgente (5)"]
    
    fifo_means = []
    pri_means = []
    fifo_cis = []
    pri_cis = []
    
    for g in gravity_order:
        if g in priority_results["fifo"]["gravity_means"]:
            fifo_means.append(priority_results["fifo"]["gravity_means"][g]["Wq"] * 60)
            fifo_cis.append(priority_results["fifo"]["gravity_ci95"][g]["Wq"])
        else:
            fifo_means.append(0)
            fifo_cis.append((0, 0))
        
        if g in priority_results["priority"]["gravity_means"]:
            pri_means.append(priority_results["priority"]["gravity_means"][g]["Wq"] * 60)
            pri_cis.append(priority_results["priority"]["gravity_ci95"][g]["Wq"])
        else:
            pri_means.append(0)
            pri_cis.append((0, 0))
    
    fifo_cis = np.array(fifo_cis).T
    pri_cis = np.array(pri_cis).T
    
    # Ensure error bars are non-negative
    fifo_err_lower = np.maximum(0, fifo_means - fifo_cis[0])
    fifo_err_upper = np.maximum(0, fifo_cis[1] - fifo_means)
    pri_err_lower = np.maximum(0, pri_means - pri_cis[0])
    pri_err_upper = np.maximum(0, pri_cis[1] - pri_means)
    
    x = np.arange(len(gravity_labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    bars1 = ax.bar(x - width/2, fifo_means, width, label='Sin prioridad (FIFO)', 
                   color='lightcoral', edgecolor='black', alpha=0.8,
                   yerr=[fifo_err_lower, fifo_err_upper], capsize=5)
    bars2 = ax.bar(x + width/2, pri_means, width, label='Con prioridad (gravedad)', 
                   color='mediumseagreen', edgecolor='black', alpha=0.8,
                   yerr=[pri_err_lower, pri_err_upper], capsize=5)
    
    for bar, val in zip(bars1, fifo_means):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{val:.1f}', ha='center', va='bottom', fontsize=9)
    for bar, val in zip(bars2, pri_means):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{val:.1f}', ha='center', va='bottom', fontsize=9)
    
    ax.set_ylabel('Tiempo medio de espera en cola (min)', fontsize=12)
    ax.set_xlabel('Nivel de gravedad', fontsize=12)
    ax.set_title(f'Espera por gravedad: con vs. sin prioridad - {scenario_label}', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(gravity_labels)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    # Margen vertical para que las etiquetas y barras de error no se salgan
    all_tops = list(np.array(fifo_means) + fifo_cis[1]) + list(np.array(pri_means) + pri_cis[1])
    ax.set_ylim(0, max(all_tops) * 1.2 if max(all_tops) > 0 else 1)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def create_results_tables(
    analytical_results: List[Dict],
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    output_dir: str = "output"
) -> Dict[str, pd.DataFrame]:
    os.makedirs(output_dir, exist_ok=True)
    
    tables = {}
    
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    
    rows = []
    for r in analytical_results:
        if r["is_stable"]:
            for s in r["stages"]:
                rows.append({
                    "c3": r["c3"],
                    "c5": r["c5"],
                    "Etapa": s["name"],
                    "λ_eff (pac/h)": round(s["lambda_eff"], 2),
                    "μ (pac/h)": s["mu"],
                    "c": s["c"],
                    "ρ": round(s["rho"], 4),
                    "Wq (min)": round(s["Wq"] * 60, 2),
                    "W (min)": round(s["W"] * 60, 2),
                    "Lq": round(s["Lq"], 2),
                    "L": round(s["L"], 2),
                    "Cuello botella": "Sí" if s["is_bottleneck"] else "No"
                })
    
    tables["analytical_detail"] = pd.DataFrame(rows)
    tables["analytical_detail"].to_csv(f"{output_dir}/tabla_analitico_detalle.csv", index=False)
    
    summary_rows = []
    for r in analytical_results:
        if r["is_stable"]:
            bn = r["stages"][r["bottleneck_idx"]]["name"] if r["bottleneck_idx"] >= 0 else "N/A"
            summary_rows.append({
                "c3": r["c3"],
                "c5": r["c5"],
                "Estable": "Sí",
                "Cuello de botella": bn,
                "ρ_max": round(max(s["rho"] for s in r["stages"]), 4),
                "W_sistema (min)": round(r["W_system"] * 60, 2),
                "L_total": round(r["total_L"], 2)
            })
        else:
            summary_rows.append({
                "c3": r["c3"],
                "c5": r["c5"],
                "Estable": "No",
                "Cuello de botella": "Inestable",
                "ρ_max": round(max(s["rho"] for s in r["stages"]), 4),
                "W_sistema (min)": "∞",
                "L_total": "∞"
            })
    
    tables["analytical_summary"] = pd.DataFrame(summary_rows)
    tables["analytical_summary"].to_csv(f"{output_dir}/tabla_analitico_resumen.csv", index=False)
    
    val_rows = []
    for label, val in validation_results.items():
        comp = val["comparison"]
        for stage_name, data in comp.items():
            if stage_name != "overall_passed" and stage_name != "abs_tol_min":
                val_rows.append({
                    "Escenario": label,
                    "Etapa": stage_name,
                    "Wq_analitico (min)": round(data["analytical_Wq"] * 60, 2),
                    "Wq_simulacion (min)": round(data["simulation_Wq_mean"] * 60, 2),
                    "Diff_%": round(data["diff_pct"] * 100, 2),
                    "Diff_abs (min)": round(data.get("abs_diff_min",
                                                     abs(data["analytical_Wq"] - data["simulation_Wq_mean"]) * 60), 3),
                    "En_IC95": "Sí" if data["in_ci"] else "No",
                    "Validación": "PASA" if data["passed"] else "FALLA"
                })
    
    tables["validation"] = pd.DataFrame(val_rows)
    tables["validation"].to_csv(f"{output_dir}/tabla_validacion.csv", index=False)
    
    pri_rows = []
    for label, pri in priority_results.items():
        for g_name, comp in pri["gravity_comparison"].items():
            pri_rows.append({
                "Escenario": label,
                "Gravedad": g_name,
                "Wq_sin_prioridad (min)": round(comp["fifo_Wq"] * 60, 2),
                "Wq_con_prioridad (min)": round(comp["priority_Wq"] * 60, 2),
                "Diferencia (min)": round(comp["difference"] * 60, 2),
                "Mejora_%": round(comp["improvement_pct"], 1)
            })
    
    tables["priority_comparison"] = pd.DataFrame(pri_rows)
    tables["priority_comparison"].to_csv(f"{output_dir}/tabla_prioridad.csv", index=False)
    
    print(f"\nTablas guardadas en {output_dir}/")
    for name, df in tables.items():
        print(f"  - {name}: {len(df)} filas")
    
    return tables

# ============================================================================
# GRAFICAS NUEVAS: validacion por escenario y comparacion de escenarios
# ============================================================================

def plot_validation_by_stage(
    analytical: Dict[str, Any],
    simulation: Dict[str, Any],
    scenario_label: str,
    save_path: Optional[str] = None
):
    """Compara Wq analitico vs Wq simulado (con IC95) por etapa para un escenario."""
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]

    an_wq = [s["Wq"] * 60 for s in analytical["stages"]]
    sim_wq = [m["Wq"] * 60 for m in simulation["stage_means"]]
    ci_low = np.array([c["Wq"][0] * 60 for c in simulation["stage_ci95"]])
    ci_high = np.array([c["Wq"][1] * 60 for c in simulation["stage_ci95"]])
    sim_err = np.vstack([np.maximum(0, np.array(sim_wq) - ci_low),
                         np.maximum(0, ci_high - np.array(sim_wq))])

    x = np.arange(len(stage_names))
    width = 0.38

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    bars1 = ax.bar(x - width / 2, an_wq, width, label='Analitico (Erlang C)',
                   color=COLOR_ANALITICO, edgecolor='black', alpha=0.85)
    bars2 = ax.bar(x + width / 2, sim_wq, width, label='Simulacion (media +/- IC95)',
                   color=COLOR_SIMULACION, edgecolor='black', alpha=0.85,
                   yerr=sim_err, capsize=4)

    for bar, val in zip(bars1, an_wq):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                f'{val:.2f}', ha='center', va='bottom', fontsize=9)
    # Etiqueta de simulacion sobre el extremo de la barra de error (evita solape)
    tops = np.maximum(np.array(sim_wq), ci_high)
    for bar, top, val in zip(bars2, tops, sim_wq):
        ax.text(bar.get_x() + bar.get_width() / 2, top + 0.04,
                f'{val:.2f}', ha='center', va='bottom', fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(stage_names)
    ax.set_ylabel('Espera en cola Wq (min)', fontsize=12)
    ax.set_xlabel('Etapa', fontsize=12)
    ax.set_title(f'Validacion analitico vs simulacion - escenario "{scenario_label}"', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(max(an_wq), max(ci_high)) * 1.25 if max(an_wq) > 0 else 1)

    if save_path:
        plt.savefig(save_path, dpi=300)
    plt.close()


def plot_validation_summary(
    validation_results: Dict[str, Any],
    save_path: Optional[str] = None
):
    """Panel 1x3: validacion analitico vs simulacion para cada escenario."""
    labels = list(validation_results.keys())
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    x = np.arange(len(stage_names))
    width = 0.38

    fig, axes = plt.subplots(1, len(labels), figsize=(6.2 * len(labels), 5.2),
                             constrained_layout=True, sharey=True)
    if len(labels) == 1:
        axes = [axes]

    for ax, label in zip(axes, labels):
        val = validation_results[label]
        an_wq = [s["Wq"] * 60 for s in val["analytical"]["stages"]]
        sim_wq = [m["Wq"] * 60 for m in val["simulation"]["stage_means"]]
        ci_low = np.array([c["Wq"][0] * 60 for c in val["simulation"]["stage_ci95"]])
        ci_high = np.array([c["Wq"][1] * 60 for c in val["simulation"]["stage_ci95"]])
        sim_err = np.vstack([np.maximum(0, np.array(sim_wq) - ci_low),
                             np.maximum(0, ci_high - np.array(sim_wq))])

        ax.bar(x - width / 2, an_wq, width, label='Analitico',
               color=COLOR_ANALITICO, edgecolor='black', alpha=0.85)
        ax.bar(x + width / 2, sim_wq, width, label='Simulacion +/- IC95',
               color=COLOR_SIMULACION, edgecolor='black', alpha=0.85,
               yerr=sim_err, capsize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(stage_names, rotation=45, ha='right', fontsize=9)
        ax.set_title(f'{label}', fontsize=12)
        ax.grid(axis='y', alpha=0.3)

    axes[0].set_ylabel('Espera en cola Wq (min)', fontsize=12)
    axes[0].legend(fontsize=9)
    fig.suptitle('Validacion del modelo: Wq analitico vs simulacion por escenario', fontsize=14)

    if save_path:
        plt.savefig(save_path, dpi=300)
    plt.close()


def plot_scenario_comparison(
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    save_path: Optional[str] = None
):
    """Figura comparativa de los 3 escenarios (3 paneles):
       A) W_sistema: analitico vs simulacion (+/- IC95)
       B) Utilizacion rho por etapa para cada escenario
       C) Throughput: FIFO vs prioridad
    """
    labels = list(validation_results.keys())
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    x_lab = np.arange(len(labels))

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6), constrained_layout=True)

    # --- Panel A: W_sistema analitico vs simulacion
    ax = axes[0]
    an_W = [validation_results[l]["analytical"]["W_system"] * 60 for l in labels]
    sim_W = [validation_results[l]["simulation"]["W_system_mean"] * 60 for l in labels]
    ci_low = np.array([validation_results[l]["simulation"]["W_system_ci95"][0] * 60 for l in labels])
    ci_high = np.array([validation_results[l]["simulation"]["W_system_ci95"][1] * 60 for l in labels])
    err = np.vstack([np.maximum(0, np.array(sim_W) - ci_low),
                     np.maximum(0, ci_high - np.array(sim_W))])

    b1 = ax.bar(x_lab - 0.19, an_W, 0.38, label='Analitico',
                color=COLOR_ANALITICO, edgecolor='black', alpha=0.85)
    b2 = ax.bar(x_lab + 0.19, sim_W, 0.38, label='Simulacion +/- IC95',
                color=COLOR_SIMULACION, edgecolor='black', alpha=0.85, yerr=err, capsize=4)
    for bar, val in zip(b1, an_W):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f'{val:.1f}', ha='center', va='bottom', fontsize=9)
    tops = np.maximum(np.array(sim_W), ci_high)
    for bar, top, val in zip(b2, tops, sim_W):
        ax.text(bar.get_x() + bar.get_width() / 2, top + 0.4,
                f'{val:.1f}', ha='center', va='bottom', fontsize=9)
    ax.set_xticks(x_lab)
    ax.set_xticklabels(labels)
    ax.set_ylabel('Tiempo en sistema W (min)', fontsize=11)
    ax.set_title('A) Tiempo en sistema por escenario', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(max(an_W), max(ci_high)) * 1.25)

    # --- Panel B: rho por etapa para cada escenario
    ax = axes[1]
    x_stage = np.arange(len(stage_names))
    n = len(labels)
    width_b = 0.8 / n
    for k, label in enumerate(labels):
        rhos = [s["rho"] for s in validation_results[label]["analytical"]["stages"]]
        ax.bar(x_stage - 0.4 + width_b * (k + 0.5), rhos, width_b,
               label=label, color=COLORES_ESCENARIO[k % len(COLORES_ESCENARIO)],
               edgecolor='black', alpha=0.85)
    ax.axhline(y=0.85, color='orange', linestyle=':', linewidth=1.2,
               label='Umbral recomendado (0.85)')
    ax.set_xticks(x_stage)
    ax.set_xticklabels(stage_names, rotation=30, ha='right', fontsize=9)
    ax.set_ylabel('Utilizacion (rho)', fontsize=11)
    ax.set_title('B) Utilizacion por etapa y escenario', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)

    # --- Panel C: throughput FIFO vs prioridad
    ax = axes[2]
    if priority_results:
        thr_fifo = [priority_results[l]["fifo"]["throughput_per_hour"] for l in labels
                    if l in priority_results]
        thr_pri = [priority_results[l]["priority"]["throughput_per_hour"] for l in labels
                   if l in priority_results]
        lab_pri = [l for l in labels if l in priority_results]
        xp = np.arange(len(lab_pri))
        b1 = ax.bar(xp - 0.19, thr_fifo, 0.38, label='FIFO',
                    color=COLOR_FIFO, edgecolor='black', alpha=0.85)
        b2 = ax.bar(xp + 0.19, thr_pri, 0.38, label='Prioridad por gravedad',
                    color=COLOR_PRIORIDAD, edgecolor='black', alpha=0.85)
        for bar, val in zip(b1, thr_fifo):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                    f'{val:.2f}', ha='center', va='bottom', fontsize=9)
        for bar, val in zip(b2, thr_pri):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                    f'{val:.2f}', ha='center', va='bottom', fontsize=9)
        ax.set_xticks(xp)
        ax.set_xticklabels(lab_pri)
        ax.set_ylim(0, max(max(thr_fifo, key=float), max(thr_pri, key=float)) * 1.2)
    ax.set_ylabel('Pacientes completados / hora', fontsize=11)
    ax.set_title('C) Throughput: FIFO vs prioridad', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)

    fig.suptitle('Comparacion de escenarios de personal (c3 medicos / c5 enfermeros)', fontsize=14)

    if save_path:
        plt.savefig(save_path, dpi=300)
    plt.close()
