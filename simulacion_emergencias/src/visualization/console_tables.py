"""
Impresión de tablas y resúmenes de resultados en la TERMINAL.

Aquí vive todo lo que se muestra en consola al final de la corrida:
  1. Resumen del barrido analítico (todas las configuraciones c3 x c5)
  2. Detalle por etapa de los escenarios seleccionados
  3. Validación analítico vs simulación
  4. Comparación FIFO vs prioridad por gravedad
  5. Resumen de corrida por escenario (lectura rápida) con mini-gráficas
     de colas en ASCII

Diseñado para ser TOLERANTE: acepta estructuras de datos detalladas
(valores dict por etapa) y simples (valores numéricos), y nunca detiene
la corrida por un error de formato en los reportes.

Los CSV se siguen guardando igual en visualization.plots.create_results_tables.
"""

from typing import List, Dict, Any
import pandas as pd

WIDTH = 78

GRAVITY_LABELS = {
    "CRITICAL": "Critico (1)",
    "URGENT": "Urgente (2)",
    "MODERATE": "Moderado (3)",
    "MILD": "Leve (4)",
    "NON_URGENT": "No urgente (5)",
}


# ----------------------------------------------------------------------
# Utilidades internas
# ----------------------------------------------------------------------

def _banner(title: str):
    print("\n" + "=" * WIDTH)
    print(title)
    print("=" * WIDTH)


def _print_df(df: pd.DataFrame):
    print(df.to_string(index=False))


def _find_result(analytical_results: List[Dict], c3: int, c5: int):
    for r in analytical_results:
        if r["c3"] == c3 and r["c5"] == c5:
            return r
    return None


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _num_or_dash(v, scale: float = 1.0, ndigits: int = 2):
    if _is_num(v):
        return round(v * scale, ndigits)
    return "-"


def _get_num(data: Dict, keys, scale: float = 1.0, ndigits: int = 2):
    """Devuelve la primera clave numérica encontrada en data (con escala)."""
    if not isinstance(data, dict):
        return "-"
    for k in keys:
        if k in data and _is_num(data[k]):
            return round(data[k] * scale, ndigits)
    return "-"


# ----------------------------------------------------------------------
# TABLA 1: barrido analítico
# ----------------------------------------------------------------------

def print_sweep_summary(analytical_results: List[Dict]):
    """Tabla 1: resumen de todas las configuraciones del barrido c3 x c5."""
    _banner("TABLA 1 | BARRIDO ANALITICO - RESUMEN POR CONFIGURACION (c3 medicos x c5 enfermeros)")

    rows = []
    for r in analytical_results:
        if not isinstance(r, dict) or "stages" not in r:
            continue
        bn = r["stages"][r["bottleneck_idx"]]["name"] if r["bottleneck_idx"] >= 0 else "N/A"
        if r["is_stable"]:
            rows.append({
                "c3": r["c3"],
                "c5": r["c5"],
                "Estable": "Si",
                "Cuello de botella": bn,
                "rho_max": round(max(s["rho"] for s in r["stages"]), 3),
                "W_sistema(min)": round(r["W_system"] * 60, 1),
                "L_total": round(r["total_L"], 2),
            })
        else:
            rows.append({
                "c3": r["c3"],
                "c5": r["c5"],
                "Estable": "NO",
                "Cuello de botella": "Inestable",
                "rho_max": round(max(s["rho"] for s in r["stages"]), 3),
                "W_sistema(min)": "-",
                "L_total": "-",
            })

    if not rows:
        print("  (sin datos del barrido analitico)")
        return

    _print_df(pd.DataFrame(rows))

    stable = [r for r in analytical_results
              if isinstance(r, dict) and r.get("is_stable")]
    print(f"\n  -> {len(stable)}/{len(analytical_results)} configuraciones estables "
          f"(rho < 1 en todas las etapas)")


# ----------------------------------------------------------------------
# TABLA 2: detalle por etapa
# ----------------------------------------------------------------------

def print_stage_detail(analytical_results: List[Dict], selected_scenarios: List[Dict]):
    """Tabla 2: detalle por etapa solo de los escenarios seleccionados."""
    _banner("TABLA 2 | DETALLE POR ETAPA - ESCENARIOS SELECCIONADOS")

    for scen in selected_scenarios:
        r = _find_result(analytical_results, scen["c3"], scen["c5"])
        if r is None:
            continue

        bn_name = r["stages"][r["bottleneck_idx"]]["name"] if r["bottleneck_idx"] >= 0 else "N/A"
        print(f"\n--- ESCENARIO: {scen['label'].upper()} "
              f"(c3={scen['c3']} medicos, c5={scen['c5']} enfermeros) "
              f"| Cuello de botella: {bn_name} ---")

        rows = []
        for s in r["stages"]:
            rows.append({
                "Etapa": s["name"],
                "lambda(pac/h)": round(s["lambda_eff"], 2),
                "mu(pac/h)": s["mu"],
                "c": s["c"],
                "rho": round(s["rho"], 3),
                "Wq(min)": round(s["Wq"] * 60, 2),
                "W(min)": round(s["W"] * 60, 2),
                "Lq": round(s["Lq"], 2),
                "L": round(s["L"], 2),
                "CuelloBotella": "SI" if s["is_bottleneck"] else "no",
            })

        _print_df(pd.DataFrame(rows))
        print(f"  W total en sistema: {r['W_system'] * 60:.1f} min "
              f"| L total: {r['total_L']:.2f} pacientes")


# ----------------------------------------------------------------------
# TABLA 3: validación (tolerante a estructuras dict o float)
# ----------------------------------------------------------------------

def _row_from_stage_data(label: str, stage_name: str, data: Dict) -> Dict:
    """Fila de validación a partir de un dict detallado de una etapa."""
    in_ci = data.get("in_ci")
    passed = data.get("passed")
    return {
        "Escenario": label,
        "Etapa": stage_name,
        "Wq_analitico(min)": _get_num(data, ("analytical_Wq", "Wq_analitico", "analytical"), 60),
        "Wq_simulacion(min)": _get_num(data, ("simulation_Wq_mean", "Wq_simulacion", "simulation"), 60),
        "Diff(%)": _get_num(data, ("diff_pct", "diff", "difference"), 100),
        "En_IC95": "Si" if in_ci else ("No" if in_ci is not None else "-"),
        "Resultado": ("PASA" if passed else "FALLA") if passed is not None else "-",
    }


def print_validation(validation_results: Dict[str, Any]):
    """Tabla 3: validación analítico vs simulación.

    Soporta dos estructuras de comparison:
      A) valores dict por etapa (con analytical_Wq, diff_pct, etc.)
      B) valores numéricos por etapa (p.ej. solo la diferencia)
    """
    _banner("TABLA 3 | VALIDACION: MODELO ANALITICO VS SIMULACION (FIFO)")

    rows = []
    scalar_details = {}   # label -> [(clave, valor), ...]
    overall = {}          # label -> bool

    for label, val in validation_results.items():
        if not isinstance(val, dict):
            continue

        comp = val.get("comparison", {})
        if not isinstance(comp, dict):
            comp = {}

        if isinstance(comp.get("overall_passed"), bool):
            overall[label] = comp["overall_passed"]

        for stage_name, data in comp.items():
            if stage_name == "overall_passed":
                continue
            if isinstance(data, dict):
                rows.append(_row_from_stage_data(label, stage_name, data))
            elif _is_num(data):
                scalar_details.setdefault(label, []).append((stage_name, data))

    if rows:
        _print_df(pd.DataFrame(rows))
    elif not scalar_details and not overall:
        print("  (sin datos de validacion)")
        return

    for label in validation_results:
        if label not in overall and label not in scalar_details:
            continue
        ok = overall.get(label)
        if ok is True:
            estado = "PASO (simulacion confirma al modelo analitico)"
        elif ok is False:
            estado = "FALLO (revisar)"
        else:
            estado = "sin veredicto global"
        print(f"  -> {label:<12} validacion global: {estado}")
        if label in scalar_details:
            det = " | ".join(f"{k}={v:.4g}" for k, v in scalar_details[label])
            print(f"     metricas por etapa: {det}")


# ----------------------------------------------------------------------
# TABLA 4: prioridad (con reconstrucción si falta gravity_comparison)
# ----------------------------------------------------------------------

def _build_gravity_comparison(pri: Dict) -> Dict:
    """Reconstruye la comparación FIFO vs prioridad desde gravity_means."""
    fifo = pri.get("fifo") if isinstance(pri.get("fifo"), dict) else {}
    prio = pri.get("priority") if isinstance(pri.get("priority"), dict) else {}
    fifo_gm = fifo.get("gravity_means", {}) if isinstance(fifo, dict) else {}
    pri_gm = prio.get("gravity_means", {}) if isinstance(prio, dict) else {}

    gc = {}
    for g in set(list(fifo_gm.keys()) + list(pri_gm.keys())):
        f_data = fifo_gm.get(g) if isinstance(fifo_gm.get(g), dict) else {}
        p_data = pri_gm.get(g) if isinstance(pri_gm.get(g), dict) else {}
        f = f_data.get("Wq") if isinstance(f_data, dict) else None
        p = p_data.get("Wq") if isinstance(p_data, dict) else None
        if not _is_num(f) or not _is_num(p):
            continue
        gc[g] = {
            "fifo_Wq": f,
            "priority_Wq": p,
            "difference": p - f,
            "improvement_pct": ((f - p) / f * 100) if f > 0 else 0.0,
        }
    return gc


def print_priority(priority_results: Dict[str, Any]):
    """Tabla 4: comparación FIFO vs prioridad por gravedad."""
    _banner("TABLA 4 | ESPERA EN COLA POR GRAVEDAD: FIFO vs PRIORIDAD NO EXPROPIATIVA")

    rows = []
    for label, pri in priority_results.items():
        if not isinstance(pri, dict):
            continue

        gc = pri.get("gravity_comparison")
        if not isinstance(gc, dict) or not gc:
            gc = _build_gravity_comparison(pri)

        for g_name, comp in gc.items():
            if not isinstance(comp, dict):
                continue
            fifo_wq = comp.get("fifo_Wq")
            pri_wq = comp.get("priority_Wq")
            if not _is_num(fifo_wq) or not _is_num(pri_wq):
                continue
            diff = comp.get("difference")
            if not _is_num(diff):
                diff = pri_wq - fifo_wq
            imp = comp.get("improvement_pct")
            if not _is_num(imp):
                imp = ((fifo_wq - pri_wq) / fifo_wq * 100) if fifo_wq > 0 else 0.0
            rows.append({
                "Escenario": label,
                "Gravedad": GRAVITY_LABELS.get(g_name, g_name),
                "Wq_FIFO(min)": round(fifo_wq * 60, 2),
                "Wq_Prioridad(min)": round(pri_wq * 60, 2),
                "Diferencia(min)": round(diff * 60, 2),
                "Mejora(%)": round(imp, 1),
            })

    if not rows:
        print("  (sin datos de comparacion de prioridad)")
        return

    _print_df(pd.DataFrame(rows))

    print("  -> Mejora(%) > 0: la prioridad reduce la espera de ese grupo.")
    print("     Los pacientes criticos/urgentes esperan menos; los leves, un poco mas.")


# ----------------------------------------------------------------------
# Resumen de corrida por escenario
# ----------------------------------------------------------------------

def print_run_summaries(
    analytical_results: List[Dict],
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    selected_scenarios: List[Dict]
):
    """Resumen de corrida por escenario: lectura rápida + mini-colas ASCII."""
    _banner("RESUMEN DE CORRIDA POR ESCENARIO (LECTURA RAPIDA)")

    for scen in selected_scenarios:
        c3, c5, label = scen["c3"], scen["c5"], scen["label"]
        r = _find_result(analytical_results, c3, c5)
        if r is None:
            continue

        bn_name = r["stages"][r["bottleneck_idx"]]["name"] if r["bottleneck_idx"] >= 0 else "N/A"

        print(f"\n  ESCENARIO: {label.upper()}")
        print(f"  Personal.......: {c3} medicos (consulta), {c5} enfermeros (tratamiento)")
        print(f"  Estable........: {'Si' if r['is_stable'] else 'NO (rho >= 1)'}")
        print(f"  Cuello botella.: {bn_name} "
              f"(rho = {max(s['rho'] for s in r['stages']):.3f})")
        print(f"  W en sistema...: {r['W_system'] * 60:.1f} min por paciente")
        print(f"  L total........: {r['total_L']:.2f} pacientes dentro del sistema")

        val = validation_results.get(label) if isinstance(validation_results, dict) else None
        if isinstance(val, dict):
            comp = val.get("comparison", {})
            if isinstance(comp, dict) and isinstance(comp.get("overall_passed"), bool):
                ok = comp["overall_passed"]
                print(f"  Validacion.....: "
                      f"{'PASO (simulacion confirma al analitico)' if ok else 'FALLO (revisar)'}")

        pri = priority_results.get(label) if isinstance(priority_results, dict) else None
        if isinstance(pri, dict):
            gc = pri.get("gravity_comparison")
            if not isinstance(gc, dict) or not gc:
                gc = _build_gravity_comparison(pri)
            cri = gc.get("CRITICAL") if isinstance(gc, dict) else None
            if isinstance(cri, dict) and _is_num(cri.get("fifo_Wq")) and _is_num(cri.get("priority_Wq")):
                imp = cri.get("improvement_pct")
                if not _is_num(imp):
                    imp = ((cri["fifo_Wq"] - cri["priority_Wq"]) / cri["fifo_Wq"] * 100) \
                        if cri["fifo_Wq"] > 0 else 0.0
                print(f"  Paciente CRITICO: espera FIFO = {cri['fifo_Wq'] * 60:.1f} min "
                      f"-> con prioridad = {cri['priority_Wq'] * 60:.1f} min "
                      f"({imp:.0f}% de mejora)")

        # Mini-cola ASCII: pacientes esperando (Lq) en cada etapa
        lqs = [s["Lq"] for s in r["stages"]]
        lq_max = max(lqs) if lqs else 0
        print(f"  Cola promedio por etapa (Lq, pacientes esperando):")
        for s in r["stages"]:
            n = int(round(s["Lq"] / lq_max * 28)) if lq_max > 0 else 0
            print(f"    {s['name']:<13} {s['Lq']:6.2f}  |{'#' * n}")

    print("\n" + "-" * WIDTH)
    print("NOTA: Wq = espera en cola | W = espera total | Lq = pacientes en cola |")
    print("      L = pacientes en el sistema | rho = utilizacion del servidor")


# ----------------------------------------------------------------------
# Orquestador
# ----------------------------------------------------------------------

def print_all_console_tables(
    analytical_results: List[Dict],
    validation_results: Dict[str, Any],
    priority_results: Dict[str, Any],
    selected_scenarios: List[Dict]
):
    """Punto de entrada: imprime en orden todas las tablas + resumen de corrida.

    Cada sección está protegida: si una estructura de datos no es la
    esperada, se avisa en consola pero la corrida NUNCA se detiene.
    """
    secciones = [
        ("la Tabla 1 (barrido analitico)",
         lambda: print_sweep_summary(analytical_results)),
        ("la Tabla 2 (detalle por etapa)",
         lambda: print_stage_detail(analytical_results, selected_scenarios)),
        ("la Tabla 3 (validacion)",
         lambda: print_validation(validation_results)),
        ("la Tabla 4 (prioridad)",
         lambda: print_priority(priority_results)),
        ("el Resumen de corrida",
         lambda: print_run_summaries(analytical_results, validation_results,
                                     priority_results, selected_scenarios)),
    ]

    for nombre, fn in secciones:
        try:
            fn()
        except Exception as e:
            print(f"\n  [aviso] No se pudo mostrar {nombre}: "
                  f"{type(e).__name__}: {e}")
            