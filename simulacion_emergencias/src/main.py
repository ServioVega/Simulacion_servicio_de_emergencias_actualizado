#!/usr/bin/env python3
"""
Modelado y Análisis de un Servicio de Emergencias Hospitalarias
mediante Redes de Colas Abiertas para la Identificación de Cuellos
de Botella y Optimización de Personal

Autores: Flores Gallardo Emilio Josue, Pardo Lima Steeven Daniel,
         Vega Jimenez Servio Julian, Valarezo Roman Maria del Cisne
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import load_parameters
from experiments import run_full_experiment, find_min_stable_staffing
from visualization import (
    plot_utilization_by_stage,
    plot_wait_vs_doctors,
    plot_wait_by_gravity,
    create_results_tables,
    print_all_console_tables
)


def main():
    print("=" * 70)
    print("MODELADO DE SERVICIO DE EMERGENCIAS - REDES DE COLAS DE JACKSON")
    print("=" * 70)
    
    # Permite pasar un config opcional: python -m src.main config/quick_parameters.yaml
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/base_parameters.yaml"
    params = load_parameters(config_path)
    print(f"\nConfiguracion cargada: {params.simulation.replications} replicas, "
          f"{params.simulation.horizon_hours}h horizonte, "
          f"{params.simulation.warmup_hours}h warm-up")
    
    print("\n" + "=" * 70)
    print("EJECUTANDO EXPERIMENTO COMPLETO")
    print("=" * 70)
    
    result = run_full_experiment(params)
    
    print("\n" + "=" * 70)
    print("BÚSQUEDA DE PERSONAL MÍNIMO ESTABLE")
    print("=" * 70)
    
    min_staff = find_min_stable_staffing(result.analytical_results, max_W_system=120)
    if min_staff["found"]:
        print(f"\nConfiguracion minima estable (W < 120 min):")
        print(f"  Medicos (c3): {min_staff['c3']}")
        print(f"  Enfermeros (c5): {min_staff['c5']}")
        print(f"  Tiempo en sistema: {min_staff['W_system_min']:.1f} min")
        print(f"  Cuello de botella: {min_staff['bottleneck']}")
    else:
        print(f"\n{min_staff['message']}")
    
    if result.analytical_results:
        print("\n" + "=" * 70)
        print("GENERANDO GRAFICAS")
        print("=" * 70)
        
        first_scenario = result.analytical_results[0]
        c3_ref = first_scenario["c3"]
        c5_ref = first_scenario["c5"]
        
        print("\n1. Utilizacion por etapa (escenario base)...")
        plot_utilization_by_stage(result.analytical_results, c3_ref, c5_ref,
                                  save_path="output/grafica_utilizacion.png")
        
        print("\n2. Espera vs. medicos (c5 fijo)...")
        plot_wait_vs_doctors(result.analytical_results, fixed_c5=c5_ref,
                             save_path="output/grafica_espera_vs_medicos.png")
        
        if result.priority_results:
            first_pri_label = list(result.priority_results.keys())[0]
            print(f"\n3. Espera por gravedad (con vs sin prioridad) - {first_pri_label}...")
            plot_wait_by_gravity(result.priority_results[first_pri_label], first_pri_label,
                                 save_path="output/grafica_espera_gravedad.png")
    
    print("\n" + "=" * 70)
    print("MOSTRANDO RESULTADOS EN CONSOLA")
    print("=" * 70)
    
    print_all_console_tables(
        result.analytical_results,
        result.validation_results,
        result.priority_results,
        params.parameter_sweep.selected_scenarios
    )
    
    print("\n" + "=" * 70)
    print("GUARDANDO TABLAS EN CSV (carpeta output/)")
    print("=" * 70)
    
    create_results_tables(
        result.analytical_results,
        result.validation_results,
        result.priority_results,
        output_dir="output"
    )
    
    print("\n" + "=" * 70)
    print("EXPERIMENTO COMPLETADO EXITOSAMENTE")
    print("=" * 70)


if __name__ == "__main__":
    main()
    