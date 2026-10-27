import pytest
import numpy as np
from src.models.entities import Patient, GravityLevel, SimulationMetrics, StageConfig
from src.simulation.priority_strategy import (
    FIFOStrategy, PriorityNonPreemptiveStrategy, create_strategy
)


class TestEntities:
    def test_patient_creation(self):
        p = Patient(id=1, gravity=GravityLevel.CRITICAL, arrival_time=0.0)
        assert p.id == 1
        assert p.gravity == GravityLevel.CRITICAL
        assert p.current_stage == 0

    def test_patient_wait_calculation(self):
        p = Patient(id=1, gravity=GravityLevel.URGENT, arrival_time=0.0)
        p.wait_times = [2.0, 3.0, 1.0]
        p.service_times = [5.0, 4.0]
        assert p.total_wait == 6.0
        assert p.total_service == 9.0
        assert p.total_time == 15.0

    def test_gravity_level_order(self):
        assert GravityLevel.CRITICAL < GravityLevel.URGENT
        assert GravityLevel.URGENT < GravityLevel.MODERATE
        assert GravityLevel.MODERATE < GravityLevel.MILD
        assert GravityLevel.MILD < GravityLevel.NON_URGENT

    def test_simulation_metrics(self):
        m = SimulationMetrics()
        m.record_stage_wait(0, 2.5)
        m.record_stage_wait(0, 3.0)
        m.record_stage_service(0, 5.0)
        m.record_patient_gravity(GravityLevel.CRITICAL, 10.0, 15.0)
        
        stats = m.get_stage_stats(0)
        assert stats["Wq"] == 2.75
        
        grav_stats = m.get_gravity_stats(GravityLevel.CRITICAL)
        assert grav_stats["Wq"] == 10.0
        assert grav_stats["W"] == 15.0

    def test_stage_config(self):
        config = StageConfig(name="Test", mu=10.0, c=2, routing_probs=[0.5, 0.3])
        assert abs(config.exit_prob - 0.2) < 1e-10


class TestPriorityStrategies:
    def test_create_strategy_fifo(self):
        strat = create_strategy("fifo")
        assert isinstance(strat, FIFOStrategy)

    def test_create_strategy_priority(self):
        strat = create_strategy("priority")
        assert isinstance(strat, PriorityNonPreemptiveStrategy)

    def test_create_strategy_invalid(self):
        with pytest.raises(ValueError):
            create_strategy("invalid_mode")

    def test_priority_strategy_priority_stages(self):
        strat = create_strategy("priority", priority_stages=[1, 2])
        assert strat.priority_stages == [1, 2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])