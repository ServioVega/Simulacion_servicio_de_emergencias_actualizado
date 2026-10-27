import simpy
import numpy as np
from typing import List, Iterator
from src.models.entities import Patient, GravityLevel
from src.config.schema import BaseParameters


class PatientGenerator:
    def __init__(
        self,
        env: simpy.Environment,
        params: BaseParameters,
        patient_counter: Iterator[int],
        metrics_collector
    ):
        self.env = env
        self.params = params
        self.patient_counter = patient_counter
        self.metrics_collector = metrics_collector
        
        self.gamma = params.external_arrivals["gamma"][0]
        self.gravity_dist = params.gravity_levels.distribution
        self.gravity_levels = list(GravityLevel)
        
        self.arrival_count = 0
        self.process = env.process(self.run())

    def run(self):
        while True:
            inter_arrival = np.random.exponential(1.0 / self.gamma) if self.gamma > 0 else float('inf')
            yield self.env.timeout(inter_arrival)
            
            if self.gamma == 0:
                break
                
            gravity = GravityLevel(int(np.random.choice(self.gravity_levels, p=self.gravity_dist)))
            patient_id = next(self.patient_counter)
            
            patient = Patient(
                id=patient_id,
                gravity=gravity,
                arrival_time=self.env.now
            )
            
            self.arrival_count += 1
            self.metrics_collector.total_arrivals += 1
            
            self.metrics_collector.on_arrival(patient)
            self.env.process(self.patient_process(patient))

    def patient_process(self, patient: Patient):
        self.metrics_collector.on_patient_start(patient)
        yield self.env.process(self.metrics_collector.process_patient(patient))
        self.metrics_collector.on_patient_complete(patient)


class PatientCounter:
    def __init__(self, start: int = 0):
        self.count = start

    def __iter__(self):
        return self

    def __next__(self):
        val = self.count
        self.count += 1
        return val