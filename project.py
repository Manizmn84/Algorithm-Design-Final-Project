from typing import Dict, List, Tuple, Optional
import math
import io

INF = 10 ** 15

class Edge:
    __slots__ = ("to", "rev", "cap", "cost")
    def __init__(self, to: int, rev: int, cap: int, cost: int):
        self.to = to
        self.rev = rev
        self.cap = cap
        self.cost = cost

class MinCostMaxFlow:
    def __init__(self, n: int):
        self.n = n
        self.g: List[List[Edge]] = [[] for _ in range(n)]

    def add_edge(self, u: int, v: int, cap: int, cost: int):
        a = Edge(v, len(self.g[v]), cap, cost)
        b = Edge(u, len(self.g[u]), 0, -cost)
        self.g[u].append(a)
        self.g[v].append(b)

    def min_cost_flow(self, s: int, t: int, maxf: Optional[int] = None) -> Tuple[int, int]:
        n = self.n
        flow = 0
        cost = 0
        potential = [0] * n
        target = maxf if maxf is not None else INF

        while flow < target:
            dist = [INF] * n
            prevnode = [-1] * n
            prevedge = [-1] * n
            dist[s] = 0

            import heapq
            pq = [(0, s)]
            while pq:
                d, u = heapq.heappop(pq)
                if d != dist[u]:
                    continue
                for ei, e in enumerate(self.g[u]):
                    if e.cap <= 0:
                        continue
                    nd = d + e.cost + potential[u] - potential[e.to]
                    if nd < dist[e.to]:
                        dist[e.to] = nd
                        prevnode[e.to] = u
                        prevedge[e.to] = ei
                        heapq.heappush(pq, (nd, e.to))

            if dist[t] == INF:
                break

            for v in range(n):
                if dist[v] < INF:
                    potential[v] += dist[v]

            addf = target - flow
            v = t
            while v != s:
                u = prevnode[v]
                ei = prevedge[v]
                if u == -1:
                    addf = 0
                    break
                addf = min(addf, self.g[u][ei].cap)
                v = u
            if addf == 0:
                break

            v = t
            path_cost = 0
            while v != s:
                u = prevnode[v]
                ei = prevedge[v]
                e = self.g[u][ei]
                e.cap -= addf
                self.g[v][e.rev].cap += addf
                path_cost += e.cost
                v = u
            flow += addf
            cost += addf * path_cost

        return flow, cost

def _build_and_solve(tasks: List[Dict], nodes: List[Dict], exec_cost: Dict[str, Dict[str, float]], granularity: int = 100):
    task_ids = [t["id"] for t in tasks]
    node_ids = [n["id"] for n in nodes]

    edge_slot_demand: Dict[Tuple[int, int], int] = {}
    edge_slot_cost: Dict[Tuple[int, int], int] = {}
    max_slot_per_task = [0] * len(tasks)

    SCALE = 1000

    for ti, t in enumerate(tasks):
        cpu_i = t["cpu"]
        ram_i = t["ram"]
        local_max = 0
        for nj, nd in enumerate(nodes):
            nid = nd["id"]
            cpu_cap = nd["cpu_capacity"]
            ram_cap = nd["ram_capacity"]
            c = exec_cost.get(t["id"], {}).get(nid, float("inf"))
            if not math.isfinite(c):
                continue
            if cpu_i <= cpu_cap and ram_i <= ram_cap:
                share = max(cpu_i / max(1, cpu_cap), ram_i / max(1, ram_cap))
                sd = max(1, math.ceil(share * granularity))
                edge_slot_demand[(ti, nj)] = sd
                per_unit = int(round((c / sd) * SCALE))
                edge_slot_cost[(ti, nj)] = per_unit
                local_max = max(local_max, sd)
        max_slot_per_task[ti] = local_max

    S = 0
    T0 = 1
    N0 = T0 + len(tasks)
    K = N0 + len(nodes)
    mcmf = MinCostMaxFlow(K + 1)

    for ti in range(len(tasks)):
        cap = max_slot_per_task[ti]
        if cap > 0:
            mcmf.add_edge(S, T0 + ti, cap, 0)

    for (ti, nj), sd in edge_slot_demand.items():
        c_per = edge_slot_cost[(ti, nj)]
        mcmf.add_edge(T0 + ti, N0 + nj, sd, c_per)

    for nj in range(len(nodes)):
        mcmf.add_edge(N0 + nj, K, granularity, 0)

    flow, cost_scaled = mcmf.min_cost_flow(S, K, None)

    assignments: Dict[str, str] = {}
    total_cost = 0.0
    for ti, tid in enumerate(task_ids):
        task_v = T0 + ti
        takens = []
        for e in mcmf.g[task_v]:
            if not (N0 <= e.to < N0 + len(nodes)):
                continue
            nj = e.to - N0
            sent = mcmf.g[e.to][e.rev].cap
            sd = edge_slot_demand.get((ti, nj), 0)
            if sent > 0:
                takens.append((nj, sent, sd))
        if len(takens) == 1:
            nj, sent, sd = takens[0]
            if sent == sd and sd > 0:
                nid = node_ids[nj]
                assignments[tid] = nid
                total_cost += float(exec_cost[tid][nid])

    buf = io.StringIO()
    buf.write("Task Assignments\n")
    for tid in task_ids:
        if tid in assignments:
            buf.write(f"  {tid} -> {assignments[tid]}\n")
        else:
            buf.write(f"  {tid} -> UNASSIGNED\n")
    buf.write(f"Total Cost: {total_cost:.6f}\n")

    return {
        "text_report": buf.getvalue(),
        "assignments": assignments,
        "assigned_count": len(assignments),
        "total_cost": total_cost,
        "flow_units": flow,
    }

def solve(tasks: List[Dict], nodes: List[Dict], exec_cost: Dict[str, Dict[str, float]], granularity: int = 100) -> Dict:
    return _build_and_solve(tasks, nodes, exec_cost, granularity)

def allocate(input_data: Dict, granularity: int = 100) -> str:
    res = _build_and_solve(input_data["tasks"], input_data["nodes"], input_data["exec_cost"], granularity)
    return res["text_report"]

if __name__ == "__main__":
    demo = {
        "tasks": [
            {"id": "T1", "cpu": 2, "ram": 4, "deadline": 2},
            {"id": "T2", "cpu": 1, "ram": 2, "deadline": 3},
            {"id": "T3", "cpu": 3, "ram": 3, "deadline": 1}
        ],
        "nodes": [
            {"id": "N1", "cpu_capacity": 5, "ram_capacity": 6},
            {"id": "N2", "cpu_capacity": 3, "ram_capacity": 3}
        ],
        "exec_cost": {
            "T1": {"N1": 4, "N2": 6},
            "T2": {"N1": 3, "N2": 2},
            "T3": {"N1": 2.5, "N2": float("inf")}
        }
    }
    print(allocate(demo, granularity=100))
