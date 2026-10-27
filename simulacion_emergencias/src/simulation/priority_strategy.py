from abc import ABC, abstractmethod
from typing import List, Optional
import simpy
from src.models.entities import Patient, GravityLevel, SimulationMetrics


class PriorityStrategy(ABC):
    @abstractmethod
    def request_resource(
        self,
        env: simpy.Environment,
        resource: simpy.Resource,
        patient: Patient,
        metrics: SimulationMetrics,
        stage: int
    ) -> simpy.Event:
        pass

    @abstractmethod
    def release_resource(
        self,
        resource: simpy.Resource,
        request: simpy.events.Event
    ):
        pass


class FIFOStrategy(PriorityStrategy):
    def request_resource(self, env, resource, patient, metrics, stage):
        return resource.request()

    def release_resource(self, resource, request):
        resource.release(request)

class PriorityNonPreemptiveStrategy(PriorityStrategy):
    def __init__(self, priority_stages: List[int]):
        self.priority_stages = priority_stages

    def request_resource(self, env, resource, patient, metrics, stage):
        if stage in self.priority_stages:
            if hasattr(resource, 'request'):
                # En PriorityResource de SimPy, el valor MENOR de priority se
                # atiende primero. Gravedad 1 = critico debe ir primero, por
                # eso el valor de priority es la propia gravedad (1 < 5).
                return resource.request(priority=patient.gravity)
        return resource.request()

    def release_resource(self, resource, request):
        resource.release(request)


class PriorityQueueStoreStrategy(PriorityStrategy):
    def __init__(self, priority_stages: List[int]):
        self.priority_stages = priority_stages
        self.queues = {}

    def request_resource(self, env, resource, patient, metrics, stage):
        if stage not in self.priority_stages:
            return resource.request()
        
        if stage not in self.queues:
            self.queues[stage] = simpy.Store(env)
        
        store = self.queues[stage]
        
        def wait_for_priority():
            store.put((patient.gravity, env.now, patient))
            yield store.get()
        
        return env.process(wait_for_priority())

    def release_resource(self, resource, request):
        resource.release(request)


def create_strategy(mode: str, priority_stages: List[int] = None) -> PriorityStrategy:
    if mode == "fifo":
        return FIFOStrategy()
    elif mode == "priority":
        if priority_stages is None:
            priority_stages = [1, 2, 3, 4]
        return PriorityNonPreemptiveStrategy(priority_stages)
    elif mode == "priority_store":
        if priority_stages is None:
            priority_stages = [1, 2, 3, 4]
        return PriorityQueueStoreStrategy(priority_stages)
    else:
        raise ValueError(f"Modo de prioridad desconocido: {mode}")