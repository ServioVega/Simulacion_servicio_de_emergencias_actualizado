import numpy as np
from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class StageResult:
    name: str
    lambda_eff: float
    mu: float
    c: int
    rho: float
    erlang_c: float
    Lq: float
    Wq: float
    W: float
    L: float
    is_bottleneck: bool = False


@dataclass
class AnalyticalResult:
    stages: List[StageResult]
    total_L: float
    total_lambda: float
    W_system: float
    bottleneck_idx: int
    is_stable: bool


class ErlangC:
    @staticmethod
    def calculate(c: int, a: float) -> float:
        if c <= 0:
            raise ValueError("Número de servidores c debe ser > 0")
        if a <= 0:
            return 0.0
        
        rho = a / c
        if rho >= 1.0:
            return float('inf')
        
        # Calcular suma Σ_{k=0}^{c-1} a^k / k!
        sum_term = 0.0
        term = 1.0
        for k in range(c):
            sum_term += term
            term *= a / (k + 1)
        
        # Término a^c / (c! * (1 - rho))
        last_term = term * c / (c - a)
        
        erlang_c = last_term / (sum_term + last_term)
        return max(0.0, min(1.0, erlang_c))

    @staticmethod
    def calculate_lq(c: int, a: float, erlang_c: float) -> float:
        rho = a / c
        if rho >= 1.0 or erlang_c == float('inf'):
            return float('inf')
        return erlang_c * rho / (1.0 - rho)


class JacksonNetwork:
    def __init__(
        self,
        gamma: List[float],
        mu: List[float],
        c: List[int],
        routing: List[List[float]],
        stage_names: Optional[List[str]] = None
    ):
        self.gamma = np.array(gamma, dtype=float)
        self.mu = np.array(mu, dtype=float)
        self.c = np.array(c, dtype=int)
        self.routing = np.array(routing, dtype=float)
        self.n_stages = len(gamma)
        
        if stage_names is None:
            self.stage_names = [f"Etapa_{i+1}" for i in range(self.n_stages)]
        else:
            self.stage_names = stage_names
        
        self._validate_inputs()

    def _validate_inputs(self):
        if len(self.gamma) != self.n_stages:
            raise ValueError("gamma debe tener longitud n_stages")
        if len(self.mu) != self.n_stages:
            raise ValueError("mu debe tener longitud n_stages")
        if len(self.c) != self.n_stages:
            raise ValueError("c debe tener longitud n_stages")
        if self.routing.shape != (self.n_stages, self.n_stages):
            raise ValueError("routing debe ser matriz n_stages x n_stages")
        if any(ci <= 0 for ci in self.c):
            raise ValueError("Todos los c[i] deben ser > 0")
        if any(mi <= 0 for mi in self.mu):
            raise ValueError("Todos los mu[i] deben ser > 0")

    def solve_traffic_equations(self) -> np.ndarray:
        I = np.eye(self.n_stages)
        P_T = self.routing.T
        A = I - P_T
        
        try:
            lambda_eff = np.linalg.solve(A, self.gamma)
        except np.linalg.LinAlgError:
            raise ValueError("Sistema de ecuaciones de tráfico singular (posible red inestable)")
        
        if any(lambda_eff < -1e-10):
            raise ValueError("Llegadas efectivas negativas: red inestable")
        
        return np.maximum(lambda_eff, 0.0)

    def compute_stage_metrics(self, lambda_eff: np.ndarray) -> List[StageResult]:
        results = []
        
        for i in range(self.n_stages):
            lam = lambda_eff[i]
            mu_i = self.mu[i]
            c_i = self.c[i]
            
            a = lam / mu_i
            rho = a / c_i
            
            if rho >= 1.0:
                results.append(StageResult(
                    name=self.stage_names[i],
                    lambda_eff=lam,
                    mu=mu_i,
                    c=c_i,
                    rho=rho,
                    erlang_c=float('inf'),
                    Lq=float('inf'),
                    Wq=float('inf'),
                    W=float('inf'),
                    L=float('inf'),
                    is_bottleneck=False
                ))
                continue
            
            erlang_c = ErlangC.calculate(c_i, a)
            Lq = ErlangC.calculate_lq(c_i, a, erlang_c)
            Wq = Lq / lam if lam > 0 else 0.0
            W = Wq + 1.0 / mu_i
            L = lam * W
            
            results.append(StageResult(
                name=self.stage_names[i],
                lambda_eff=lam,
                mu=mu_i,
                c=c_i,
                rho=rho,
                erlang_c=erlang_c,
                Lq=Lq,
                Wq=Wq,
                W=W,
                L=L,
                is_bottleneck=False
            ))
        
        return results

    def analyze(self) -> AnalyticalResult:
        lambda_eff = self.solve_traffic_equations()
        stage_results = self.compute_stage_metrics(lambda_eff)
        
        is_stable = all(r.rho < 1.0 for r in stage_results)
        
        if is_stable:
            bottleneck_idx = max(range(self.n_stages), key=lambda i: stage_results[i].rho)
            stage_results[bottleneck_idx].is_bottleneck = True
        else:
            bottleneck_idx = -1
        
        total_L = sum(r.L for r in stage_results if not math.isinf(r.L))
        total_lambda = sum(self.gamma)
        W_system = total_L / total_lambda if total_lambda > 0 else 0.0
        
        return AnalyticalResult(
            stages=stage_results,
            total_L=total_L,
            total_lambda=total_lambda,
            W_system=W_system,
            bottleneck_idx=bottleneck_idx,
            is_stable=is_stable
        )

    def analyze_with_servers(self, c3: int, c5: int) -> AnalyticalResult:
        c_new = self.c.copy()
        c_new[2] = c3
        c_new[4] = c5
        
        network = JacksonNetwork(
            gamma=self.gamma.tolist(),
            mu=self.mu.tolist(),
            c=c_new.tolist(),
            routing=self.routing.tolist(),
            stage_names=self.stage_names
        )
        return network.analyze()


def create_base_network(params) -> JacksonNetwork:
    stage_names = ["Registro", "Triaje", "Consulta", "Laboratorio", "Tratamiento"]
    return JacksonNetwork(
        gamma=params.external_arrivals["gamma"],
        mu=params.service_rates["mu"],
        c=params.servers["c"],
        routing=params.routing_matrix["p"],
        stage_names=stage_names
    )