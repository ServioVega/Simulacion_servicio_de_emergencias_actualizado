import pytest
import numpy as np
from src.config import load_parameters
from src.models.analytical import create_base_network
from src.simulation import run_single_replication, AggregatedResults, ReplicationResult
from src.simulation.statistics import compare_analytical_vs_simulation


class TestSimulationIntegration:
    @pytest.fixture(scope="class")
    def params(self):
        return load_parameters("config/base_parameters.yaml")

    def test_single_replication_runs(self, params):
        result = run_single_replication(
            params=params,
            c3=3,
            c5=3,
            priority_mode="fifo",
            horizon_hours=200,
            warmup_hours=20,
            seed=42
        )
        
        assert "stages" in result
        assert "gravity" in result
        assert "W_system" in result
        assert result["completed_patients"] > 0

    def test_priority_mode_runs(self, params):
        result = run_single_replication(
            params=params,
            c3=5,
            c5=3,
            priority_mode="priority",
            horizon_hours=200,
            warmup_hours=20,
            seed=123
        )
        
        assert result["completed_patients"] > 0
        for g in ["CRITICAL", "URGENT", "MODERATE", "MILD", "NON_URGENT"]:
            assert g in result["gravity"]


class TestStatistics:
    def test_aggregated_results(self):
        reps = []
        for i in range(5):
            stages = [
                {"name": f"S{j}", "Wq": 0.1 + i*0.01, "W": 0.2 + i*0.01, "rho": 0.5,
                 "Lq": 1.0, "L": 2.0, "lambda_eff": 5.0, "mu": 10.0, "c": 1}
                for j in range(5)
            ]
            reps.append(ReplicationResult(
                stages=stages,
                gravity={g: {"Wq": 0.1, "W": 0.2, "count": 10} for g in ["CRITICAL", "URGENT"]},
                total_L=10.0,
                W_system=2.0,
                bottleneck_idx=2,
                completed_patients=50
            ))
        
        agg = AggregatedResults.from_replications(reps)
        
        assert len(agg.stage_means) == 5
        assert "CRITICAL" in agg.gravity_means
        assert agg.W_system_mean > 0

    def test_comparison_analytical_vs_simulation(self):
        analytical = {
            "stages": [
                {"name": "Registro", "Wq": 0.1, "rho": 0.5},
                {"name": "Triaje", "Wq": 0.2, "rho": 0.6},
                {"name": "Consulta", "Wq": 0.5, "rho": 0.8},
                {"name": "Laboratorio", "Wq": 0.15, "rho": 0.4},
                {"name": "Tratamiento", "Wq": 0.25, "rho": 0.7},
            ]
        }
        
        class MockAgg:
            stage_means = [{"Wq": 0.11}, {"Wq": 0.19}, {"Wq": 0.52}, {"Wq": 0.14}, {"Wq": 0.26}]
            stage_ci95 = [{"Wq": (0.09, 0.13)}, {"Wq": (0.17, 0.21)}, 
                         {"Wq": (0.48, 0.56)}, {"Wq": (0.12, 0.16)}, {"Wq": (0.24, 0.28)}]
        
        comparison = compare_analytical_vs_simulation(analytical, MockAgg(), threshold=0.05)
        
        assert "overall_passed" in comparison
        for stage in ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]:
            assert stage in comparison
            assert "passed" in comparison[stage]


class TestAnalyticalValidation:
    def test_known_mm1_case(self):
        net = create_base_network(load_parameters("config/base_parameters.yaml"))
        
        lam = 5.0
        mu = 10.0
        c = 1
        
        rho = lam / (c * mu)
        a = lam / mu
        
        from src.models.analytical import ErlangC
        erlang_c = ErlangC.calculate(c, a)
        Lq = ErlangC.calculate_lq(c, a, erlang_c)
        Wq = Lq / lam
        
        assert abs(rho - 0.5) < 1e-6
        assert abs(erlang_c - 0.5) < 1e-6
        assert abs(Wq - 0.1) < 1e-3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])