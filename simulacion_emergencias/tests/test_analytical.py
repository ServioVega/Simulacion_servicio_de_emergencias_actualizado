import pytest
import numpy as np
from src.models.analytical import ErlangC, JacksonNetwork, StageResult, AnalyticalResult


class TestErlangC:
    def test_erlang_c_single_server(self):
        c = ErlangC.calculate(1, 0.5)
        expected = 0.5
        assert abs(c - expected) < 1e-6

    def test_erlang_c_multiple_servers(self):
        c = ErlangC.calculate(2, 1.0)
        expected = 1.0 / 3.0  # Erlang C for c=2, a=1
        assert abs(c - expected) < 1e-6

    def test_erlang_c_high_utilization(self):
        c = ErlangC.calculate(3, 2.5)
        assert 0.5 < c < 1.0

    def test_erlang_c_zero_arrival(self):
        c = ErlangC.calculate(5, 0.0)
        assert c == 0.0

    def test_erlang_c_unstable(self):
        c = ErlangC.calculate(2, 3.0)
        assert c == float('inf')

    def test_lq_calculation(self):
        erlang_c = 0.5
        lq = ErlangC.calculate_lq(2, 1.0, erlang_c)
        expected = 0.5 * 0.5 / 0.5
        assert abs(lq - expected) < 1e-6


class TestJacksonNetwork:
    def setup_method(self):
        self.gamma = [10.0, 0.0, 0.0, 0.0, 0.0]
        self.mu = [20.0, 15.0, 8.0, 12.0, 10.0]
        self.c = [2, 2, 3, 2, 3]
        self.routing = [
            [0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.85, 0.15, 0.0],
            [0.1, 0.0, 0.0, 0.3, 0.6],
            [0.0, 0.0, 0.9, 0.0, 0.1],
            [0.05, 0.0, 0.0, 0.0, 0.0]
        ]

    def test_traffic_equations(self):
        net = JacksonNetwork(self.gamma, self.mu, self.c, self.routing)
        lambda_eff = net.solve_traffic_equations()
        
        assert len(lambda_eff) == 5
        assert all(l >= 0 for l in lambda_eff)
        assert lambda_eff[0] > 10.0  # Con realimentación, lambda_eff > gamma

    def test_full_analysis(self):
        net = JacksonNetwork(self.gamma, self.mu, self.c, self.routing)
        result = net.analyze()
        
        assert isinstance(result, AnalyticalResult)
        assert len(result.stages) == 5
        assert result.is_stable
        assert result.bottleneck_idx >= 0
        assert result.total_L > 0
        assert result.W_system > 0

    def test_bottleneck_identification(self):
        net = JacksonNetwork(self.gamma, self.mu, self.c, self.routing)
        result = net.analyze()
        
        max_rho = max(s.rho for s in result.stages)
        bottleneck_rho = result.stages[result.bottleneck_idx].rho
        assert abs(max_rho - bottleneck_rho) < 1e-6
        assert result.stages[result.bottleneck_idx].is_bottleneck

    def test_unstable_detection(self):
        c_bad = [1, 1, 1, 1, 1]
        net = JacksonNetwork(self.gamma, self.mu, c_bad, self.routing)
        result = net.analyze()
        
        assert not result.is_stable

    def test_analyze_with_servers(self):
        net = JacksonNetwork(self.gamma, self.mu, self.c, self.routing)
        result = net.analyze_with_servers(c3=5, c5=4)
        
        assert result.stages[2].c == 5
        assert result.stages[4].c == 4

    def test_mm1_known_case(self):
        gamma = [5.0, 0.0]
        mu = [10.0, 10.0]
        c = [1, 1]
        routing = [[0.0, 0.0], [0.0, 0.0]]
        
        net = JacksonNetwork(gamma, mu, c, routing, ["Q1", "Q2"])
        result = net.analyze()
        
        lam = 5.0
        mu1 = 10.0
        rho = lam / mu1
        expected_Wq = rho / (mu1 * (1 - rho))
        
        assert abs(result.stages[0].Wq - expected_Wq) < 1e-3


class TestStageResult:
    def test_stage_result_creation(self):
        s = StageResult(
            name="Test", lambda_eff=5.0, mu=10.0, c=1,
            rho=0.5, erlang_c=0.5, Lq=0.5, Wq=0.1, W=0.2, L=1.0
        )
        assert s.name == "Test"
        assert s.rho == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])