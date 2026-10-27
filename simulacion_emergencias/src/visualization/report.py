"""Reporte de resultados de la ejecucion (texto plano).

Genera output/resultados_ejecucion.txt con el consolidado de todos los
resultados del experimento: configuracion, barrido analitico, resultados
por escenario (analitico + simulacion + validacion + prioridad), busqueda
de personal minimo y archivos generados.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

STAGE_NAMES = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
GRAVITY_ORDER = ["CRITICAL", "URGENT", "MODERATE", "MILD", "NON_URGENT"]
GRAVITY_ES = {
    "CRITICAL": "Critico (1)",
    "URGENT": "Urgente (2)",
    "MODERATE": "Moderado (3)",
    "MILD": "Leve (4)",
    "NON_URGENT": "No urgente (5)",
}


def _linea(ch: str = "-", ancho: int = 100) -> str:
    return ch * ancho


def _tabla(headers: List[str], rows: List[List[str]], indent: str = "  ") -> str:
    """Tabla de texto de ancho fijo, alineada."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [indent + fmt.format(*headers)]
    out.append(indent + "  ".join("-" * w for w in widths))
    for row in rows:
        out.append(indent + fmt.format(*[str(c) for c in row]))
    return "\n".join(out)


def create_execution_report(
    params,
    analytical_results: List[Dict],
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    min_staff: Dict[str, Any],
    archivos_generados: List[str],
    save_path: str = "output/resultados_ejecucion.txt"
) -> str:
    """Construye y guarda el reporte completo de la ejecucion."""
    L = []
    sim = params.simulation

    # ------------------------------------------------------------------ encabezado
    L.append(_linea("="))
    L.append("REPORTE DE RESULTADOS DE LA EJECUCION")
    L.append("Modelado de Servicio de Emergencias - Redes de Colas de Jackson")
    L.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(_linea("="))

    # ------------------------------------------------------------------ configuracion
    L.append("")
    L.append("1. CONFIGURACION DEL SISTEMA")
    L.append(_linea())
    L.append(f"  Llegadas externas (gamma): {params.external_arrivals['gamma']} pac/h"
             f"  (solo Registro, etapa 1)")
    L.append(f"  Tasas de servicio (mu):    {params.service_rates['mu']} pac/h por servidor")
    L.append(f"  Servidores base (c):       {params.servers['c']}  "
             f"[c3=Consulta(medicos), c5=Tratamiento(enfermeros)]")
    L.append("  Distribucion de gravedad:")
    dist = params.gravity_levels.distribution
    labels = params.gravity_levels.labels
    for i, (lb, d) in enumerate(zip(labels, dist), 1):
        L.append(f"    Nivel {i} ({lb}): {d * 100:.1f}%")
    L.append(f"  Replicas: {sim.replications} | Horizonte: {sim.horizon_hours} h | "
             f"Warm-up: {sim.warmup_hours} h | Seed: {sim.random_seed}")
    L.append(f"  Umbral de validacion: {sim.validation_threshold * 100:.0f}% (dif. relativa) "
             f"con tolerancia absoluta 0.05 min + IC95")
    L.append("  Escenarios evaluados:")
    for scen in params.parameter_sweep.selected_scenarios:
        L.append(f"    - {scen['label']}: c3={scen['c3']} medicos, c5={scen['c5']} enfermeros")

    # ------------------------------------------------------------------ barrido analitico
    L.append("")
    L.append("2. BARRIDO ANALITICO (red de Jackson + Erlang C)")
    L.append(_linea())
    L.append("  Configuraciones estables (W = tiempo total en el sistema):")
    headers = ["c3", "c5", "Estable", "Cuello de botella", "rho_max",
               "W_sistema (min)", "L_total"]
    rows = []
    for r in analytical_results:
        if not r["is_stable"]:
            continue
        bn = STAGE_NAMES[r["bottleneck_idx"]] if r["bottleneck_idx"] >= 0 else "N/A"
        rows.append([r["c3"], r["c5"], "Si", bn,
                     f"{max(s['rho'] for s in r['stages']):.4f}",
                     f"{r['W_system'] * 60:.2f}", f"{r['total_L']:.2f}"])
    L.append(_tabla(headers, rows))

    # ------------------------------------------------------------------ por escenario
    L.append("")
    L.append("3. RESULTADOS POR ESCENARIO")
    L.append(_linea())

    for label, val in validation_results.items():
        an = val["analytical"]
        s = val["simulation"]
        c3 = next(st["c"] for st in an["stages"] if st["name"] == "Consulta")
        c5 = next(st["c"] for st in an["stages"] if st["name"] == "Tratamiento")

        L.append("")
        L.append(f"  3.{list(validation_results).index(label) + 1} ESCENARIO \"{label.upper()}\" "
                 f"(c3={c3} medicos, c5={c5} enfermeros)")
        L.append("  " + _linea())

        # --- analitico por etapa
        L.append("  a) Modelo analitico por etapa (Erlang C):")
        headers = ["Etapa", "lambda_eff", "c", "rho", "Wq (min)", "W (min)", "Lq", "L", "Cuello"]
        rows = []
        for st in an["stages"]:
            rows.append([st["name"], f"{st['lambda_eff']:.2f}", st["c"],
                         f"{st['rho']:.4f}", f"{st['Wq'] * 60:.3f}", f"{st['W'] * 60:.3f}",
                         f"{st['Lq']:.3f}", f"{st['L']:.3f}",
                         "SI" if st["is_bottleneck"] else "-"])
        L.append(_tabla(headers, rows))
        L.append(f"  -> W_sistema analitico: {an['W_system'] * 60:.2f} min | "
                 f"L_total: {an['total_L']:.2f} pacientes")

        # --- simulacion por etapa
        L.append("")
        L.append("  b) Simulacion por etapa (media +/- IC95 entre replicas):")
        headers = ["Etapa", "Wq sim (min)", "IC95 Wq (min)", "W sim (min)", "Lq sim"]
        rows = []
        for i, name in enumerate(STAGE_NAMES):
            ci = s["stage_ci95"][i]["Wq"]
            rows.append([name,
                         f"{s['stage_means'][i]['Wq'] * 60:.3f}",
                         f"[{ci[0] * 60:.3f}, {ci[1] * 60:.3f}]",
                         f"{s['stage_means'][i]['W'] * 60:.3f}",
                         f"{s['stage_means'][i]['Lq']:.3f}"])
        L.append(_tabla(headers, rows))
        wci = s["W_system_ci95"]
        L.append(f"  -> W_sistema simulado: {s['W_system_mean'] * 60:.2f} min "
                 f"IC95 [{wci[0] * 60:.2f}, {wci[1] * 60:.2f}]")
        L.append(f"  -> Throughput (FIFO): {s['throughput_per_hour']:.2f} pacientes/h "
                 f"({s['completed_patients_mean']:.0f} pac. completados por replica)")

        # --- validacion
        L.append("")
        L.append("  c) Validacion analitico vs simulacion (Wq por etapa):")
        comp = val["comparison"]
        headers = ["Etapa", "Wq analitico", "Wq simulacion", "Diff %", "Dif abs (min)",
                   "En IC95", "Veredicto"]
        rows = []
        for name in STAGE_NAMES:
            d = comp[name]
            rows.append([name,
                         f"{d['analytical_Wq'] * 60:.3f}",
                         f"{d['simulation_Wq_mean'] * 60:.3f}",
                         f"{d['diff_pct'] * 100:.2f}%" if d["diff_pct"] != float('inf') else "inf",
                         f"{d['abs_diff_min']:.3f}",
                         "Si" if d["in_ci"] else "No",
                         "PASA" if d["passed"] else "FALLA"])
        L.append(_tabla(headers, rows))
        veredicto = "VALIDADO" if comp["overall_passed"] else "NO VALIDADO"
        L.append(f"  -> Veredicto global del escenario: {veredicto}")

        # --- prioridad
        if label in priority_results:
            pri = priority_results[label]
            L.append("")
            L.append("  d) Comparacion FIFO vs prioridad no expropiativa (Wq por gravedad):")
            headers = ["Gravedad", "Wq FIFO (min)", "Wq Prioridad (min)",
                       "Diferencia (min)", "Mejora %"]
            rows = []
            for g in GRAVITY_ORDER:
                gc = pri["gravity_comparison"].get(g)
                if gc is None:
                    continue
                rows.append([GRAVITY_ES[g],
                             f"{gc['fifo_Wq'] * 60:.3f}",
                             f"{gc['priority_Wq'] * 60:.3f}",
                             f"{gc['difference'] * 60:+.3f}",
                             f"{gc['improvement_pct']:+.1f}%"])
            L.append(_tabla(headers, rows))
            L.append(f"  -> Throughput: FIFO {pri['fifo']['throughput_per_hour']:.2f} pac/h vs "
                     f"Prioridad {pri['priority']['throughput_per_hour']:.2f} pac/h")
            L.append("     (La prioridad mejora a los pacientes criticos a costa de los leves;"
                     " el throughput total no cambia)")

    # ------------------------------------------------------------------ personal minimo
    L.append("")
    L.append("4. BUSQUEDA DE PERSONAL MINIMO ESTABLE (W_sistema < 120 min)")
    L.append(_linea())
    if min_staff.get("found"):
        L.append(f"  Configuracion minima encontrada: c3={min_staff['c3']} medicos, "
                 f"c5={min_staff['c5']} enfermeros")
        L.append(f"  Tiempo en sistema: {min_staff['W_system_min']:.2f} min")
        L.append(f"  Cuello de botella: {min_staff['bottleneck']}")
    else:
        L.append(f"  {min_staff.get('message', 'Sin configuracion estable')}")

    # ------------------------------------------------------------------ archivos
    L.append("")
    L.append("5. ARCHIVOS GENERADOS")
    L.append(_linea())
    for f in archivos_generados:
        L.append(f"  - {f}")

    contenido = "\n".join(L)
    import os
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print(f"\nReporte de ejecucion guardado en: {save_path}")
    return contenido
