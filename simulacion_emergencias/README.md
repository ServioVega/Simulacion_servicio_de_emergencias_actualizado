# Modelado de Servicio de Emergencias - Redes de Colas de Jackson

Implementación de un modelo analítico (red de Jackson + Erlang C) y simulación de eventos discretos (SimPy) para optimización de personal en urgencias hospitalarias.

## Estructura del Proyecto

```
src/
├── config/          # Configuración y validación (YAML + Pydantic)
├── models/          # Modelo analítico y entidades
│   ├── analytical.py    # Red de Jackson + Erlang C
│   └── entities.py      # Patient, StageConfig, SimulationMetrics
├── simulation/      # Simulación SimPy con Strategy Pattern
│   ├── engine.py           # Motor de simulación principal
│   ├── priority_strategy.py # FIFO / Prioridad no expropiativa
│   ├── patient_generator.py # Generador de llegadas Poisson
│   └── statistics.py       # Agregación + IC95% + Validación
├── experiments/     # Experimentos y barridos
│   ├── runner.py    # Ejecución de réplicas
│   └── sweep.py     # Barrido c3×c5 + búsqueda mínimo
├── visualization/   # Gráficas y tablas
│   └── plots.py     # 3 gráficas requeridas + CSV
└── main.py          # Punto de entrada
```

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

Editar `config/base_parameters.yaml`:

- **external_arrivals.gamma**: Llegadas externas por hora (solo registro)
- **service_rates.mu**: Tasas de servicio por servidor/hora
- **servers.c**: Servidores por etapa (c₃=médicos, c₅=enfermeros)
- **routing_matrix.p**: Matriz de enrutamiento 5×5
- **gravity_levels.distribution**: % pacientes por gravedad (5 niveles)
- **simulation**: Réplicas, horizonte, warm-up, seed, umbral validación
- **parameter_sweep**: Rangos c₃/c₅ y escenarios seleccionados

## Ejecución

```bash
python -m src.main
```

Genera en `output/`:

**Gráficas (PNG, 300 dpi):**

| Archivo | Contenido |
|---------|-----------|
| `grafica_utilizacion_saturado.png` | Utilización por etapa — escenario saturado (c3=3, c5=3) |
| `grafica_utilizacion_equilibrado.png` | Utilización por etapa — escenario equilibrado (c3=5, c5=3) |
| `grafica_utilizacion_holgado.png` | Utilización por etapa — escenario holgado (c3=8, c5=4) |
| `grafica_utilizacion.png` | Alias del escenario de referencia (saturado) |
| `grafica_espera_vs_medicos.png` | Wq por etapa vs número de médicos (barrido c3 con c5 fijo) |
| `grafica_espera_gravedad_saturado.png` | Espera por gravedad FIFO vs prioridad — saturado |
| `grafica_espera_gravedad_equilibrado.png` | Espera por gravedad FIFO vs prioridad — equilibrado |
| `grafica_espera_gravedad_holgado.png` | Espera por gravedad FIFO vs prioridad — holgado |
| `grafica_espera_gravedad.png` | Alias del escenario de referencia (saturado) |
| `grafica_validacion_saturado.png` | Wq analítico vs simulación (± IC95) — saturado |
| `grafica_validacion_equilibrado.png` | Wq analítico vs simulación (± IC95) — equilibrado |
| `grafica_validacion_holgado.png` | Wq analítico vs simulación (± IC95) — holgado |
| `grafica_validacion_escenarios.png` | Panel 1×3 con la validación de los 3 escenarios |
| `grafica_comparacion_escenarios.png` | Comparativa: W sistema, ρ por etapa y throughput FIFO vs prioridad |

**Tablas (CSV):**

| Archivo | Contenido |
|---------|-----------|
| `tabla_analitico_detalle.csv` | Resultados analíticos completos (config × etapa) |
| `tabla_analitico_resumen.csv` | Resumen por configuración (cuello de botella, W, L) |
| `tabla_validacion.csv` | Analítico vs simulación (diff %, diff abs, IC95, veredicto) |
| `tabla_prioridad.csv` | Comparación FIFO vs prioridad por gravedad y escenario |
| `tabla_escenarios_resumen.csv` | **Una fila por escenario**: W sistema an/sim ± IC95, throughput |
| `tabla_simulacion_detalle.csv` | **Simulación por escenario y etapa** con IC95 |

**Reporte:**

- `resultados_ejecucion.txt` — consolidado de toda la ejecución: configuración, barrido analítico, resultados por escenario (analítico + simulación + validación + prioridad) y búsqueda de personal mínimo.

## Tests

```bash
pytest tests/ -v
```

## Modelo Analítico

**Red de Jackson abierta** con 5 etapas y realimentación:
1. Ecuaciones de tráfico: λ = (I - Pᵀ)⁻¹ γ
2. Cada etapa: M/M/c con Erlang C
3. Métricas: ρ, Wq, W, Lq, L (Ley de Little)
4. Cuello de botella = etapa con max ρ

## Simulación

**SimPy** - Eventos discretos con dos modos:
- **FIFO**: Validación vs modelo analítico
- **Prioridad no expropiativa**: Desde triaje, atiende más grave primero
- 30 réplicas, 1000h, warm-up 100h, seeds fijas
- IC95% para todas las métricas

## Patrones de Diseño

- **Strategy**: Modos de prioridad (FIFO / Priority)
- **Factory**: Creación de pacientes y estrategias
- **Builder**: Configuración de experimentos
- **Observer**: Recolección de métricas durante simulación
- **Template Method**: Flujo de procesamiento de paciente
- **Dependency Injection**: Configuración externa YAML