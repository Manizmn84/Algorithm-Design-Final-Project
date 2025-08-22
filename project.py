from typing import Dict, List, Tuple, Optional
import math
import io
import heapq

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

def allocate(input_data: Dict) -> str:
    tasks = input_data["tasks"]
    nodes = input_data["nodes"]
    exec_cost = input_data["exec_cost"]

    S = 0
    num_tasks = len(tasks)
    num_nodes = len(nodes)
    T_start = 1
    N_start = T_start + num_tasks
    K = N_start + num_nodes
    
    mcmf = MinCostMaxFlow(K + 1)
    
    task_map = {t['id']: i for i, t in enumerate(tasks)}
    node_map = {n['id']: i for i, n in enumerate(nodes)}

    for i in range(num_tasks):
        mcmf.add_edge(S, T_start + i, 1, 0)
    
    for t in tasks:
        task_id = t["id"]
        t_idx = task_map[task_id]
        task_cpu = t["cpu"]
        task_ram = t["ram"]

        for n in nodes:
            node_id = n["id"]
            n_idx = node_map[node_id]
            node_cpu_cap = n["cpu_capacity"]
            node_ram_cap = n["ram_capacity"]

            if task_cpu <= node_cpu_cap and task_ram <= node_ram_cap:
                cost_value = exec_cost.get(task_id, {}).get(node_id)
                if cost_value is not None and math.isfinite(cost_value):
                    mcmf.add_edge(T_start + t_idx, N_start + n_idx, 1, int(cost_value))

    for i in range(num_nodes):
        mcmf.add_edge(N_start + i, K, num_tasks, 0)

    max_flow = num_tasks
    flow, cost = mcmf.min_cost_flow(S, K, max_flow)

    assignments: Dict[str, str] = {}
    for t_idx, task in enumerate(tasks):
        task_id = task["id"]
        for edge in mcmf.g[T_start + t_idx]:
            if N_start <= edge.to < N_start + num_nodes and edge.cap == 0:
                node_id = nodes[edge.to - N_start]["id"]
                assignments[task_id] = node_id
    
    buf = io.StringIO()
    buf.write("### Phase 1 Output: Initial Task Allocation\n\n")
    buf.write("Assignments:\n")
    for task in tasks:
        task_id = task["id"]
        if task_id in assignments:
            buf.write(f"  {task_id} -> {assignments[task_id]}\n")
        else:
            buf.write(f"  {task_id} -> UNASSIGNED (Due to resource limits or no path)\n")

    buf.write(f"\nTotal Cost: {cost}\n")
    buf.write(f"Total Flow: {flow}\n")
    
    return buf.getvalue()

demo_data = {
    "tasks": [
        {"id": "T1", "cpu": 2, "ram": 4, "deadline": 2},
        {"id": "T2", "cpu": 1, "ram": 2, "deadline": 3}
    ],
    "nodes": [
        {"id": "N1", "cpu_capacity": 5, "ram_capacity": 6},
        {"id": "N2", "cpu_capacity": 3, "ram_capacity": 3}
    ],
    "exec_cost": {
        "T1": {"N1": 4, "N2": 6},
        "T2": {"N1": 3, "N2": 2}
    }
}

if __name__ == "__main__":
    print(allocate(demo_data))

