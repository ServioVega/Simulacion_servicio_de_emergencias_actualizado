"""Tablas de resultados por escenario (CSV).

Complementa las tablas generadas por plots.create_results_tables con:
  - tabla_escenarios_resumen.csv:   una fila por escenario (vision general)
  - tabla_simulacion_detalle.csv:   una fila por escenario x etapa (simulacion)
"""
import os
from typing import Dict, Any
import pandas as pd


def create_scenario_tables(
    analytical_results: list,
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    output_dir: str = "output"
) -> Dict[str, pd.DataFrame]:
    """Genera las tablas comparativas de los escenarios seleccionados."""
    os.makedirs(output_dir, exist_ok=True)
    tables = {}

    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    # Mapa (c3, c5) -> resultado analitico del barrido
    an_by_cfg = {(r["c3"], r["c5"]): r for r in analytical_results}

    # ------------------------------------------------------------------
    # 1) Resumen por escenario: una fila con las metricas clave
    # ------------------------------------------------------------------
    rows = []
    for label, val in validation_results.items():
        an = val["analytical"]
        sim = val["simulation"]
        c3 = next(s["c"] for s in an["stages"] if s["name"] == "Consulta")
        c5 = next(s["c"] for s in an["stages"] if s["name"] == "Tratamiento")

        bn_idx = an["bottleneck_idx"]
        bn_name = stage_names[bn_idx] if bn_idx >= 0 else "N/A"
        rho_max = max(s["rho"] for s in an["stages"])

        W_an = an["W_system"] * 60
        W_sim = sim["W_system_mean"] * 60
        ci = sim["W_system_ci95"]
        diff_pct = abs(W_an - W_sim) / W_an * 100 if W_an > 0 else 0.0

        pri_thr = "-"
        if label in priority_results:
            pri_thr = round(priority_results[label]["priority"]["throughput_per_hour"], 2)

        rows.append({
            "Escenario": label,
            "Medicos (c3)": c3,
            "Enfermeros (c5)": c5,
            "Estable": "Si" if an["is_stable"] else "No",
            "Cuello de botella": bn_name,
            "rho_max": round(rho_max, 4),
            "W_sistema_analitico (min)": round(W_an, 2),
            "W_sistema_simulacion (min)": round(W_sim, 2),
            "IC95_inf (min)": round(ci[0] * 60, 2),
            "IC95_sup (min)": round(ci[1] * 60, 2),
            "Diff_%": round(diff_pct, 2),
            "Throughput_FIFO (pac/h)": round(sim["throughput_per_hour"], 2),
            "Throughput_Prioridad (pac/h)": pri_thr,
        })

    tables["scenario_summary"] = pd.DataFrame(rows)
    tables["scenario_summary"].to_csv(
        f"{output_dir}/tabla_escenarios_resumen.csv", index=False, encoding="utf-8-sig"
    )

    # ------------------------------------------------------------------
    # 2) Detalle de simulacion por escenario y etapa (con IC95)
    # ------------------------------------------------------------------
    rows = []
    for label, val in validation_results.items():
        sim = val["simulation"]
        an_stages = val["analytical"]["stages"]
        for i, name in enumerate(stage_names):
            ci = sim["stage_ci95"][i]["Wq"]
            an_wq = an_stages[i]["Wq"] * 60
            sim_wq = sim["stage_means"][i]["Wq"] * 60
            rows.append({
                "Escenario": label,
                "Etapa": name,
                "c (servidores)": an_stages[i]["c"],
                "Wq_simulacion (min)": round(sim_wq, 3),
                "IC95_inf (min)": round(ci[0] * 60, 3),
                "IC95_sup (min)": round(ci[1] * 60, 3),
                "Wq_analitico (min)": round(an_wq, 3),
                "Diff_%": round(abs(an_wq - sim_wq) / an_wq * 100, 2) if an_wq > 0 else 0.0,
                "W_simulacion (min)": round(sim["stage_means"][i]["W"] * 60, 3),
                "Lq_simulacion": round(sim["stage_means"][i]["Lq"], 3),
                "rho_analitico": round(an_stages[i]["rho"], 4),
            })

    tables["simulation_detail"] = pd.DataFrame(rows)
    tables["simulation_detail"].to_csv(
        f"{output_dir}/tabla_simulacion_detalle.csv", index=False, encoding="utf-8-sig"
    )

    print(f"\nTablas de escenarios guardadas en {output_dir}/")
    for name, df in tables.items():
        print(f"  - {name}: {len(df)} filas")

    return tables
