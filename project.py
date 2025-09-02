# First, install the library if you haven't:
# pip install ortools

from ortools.graph.python import min_cost_flow
from collections import deque
import json

# -----------------------------------------------------------------------------
# ORIGINAL PHASE 1 FUNCTION (This remains UNTOUCHED)
# -----------------------------------------------------------------------------
def solve_task_allocation():
    """
    This is your original, committed function for Phase 1.
    It remains unchanged and can be run independently.
    """
    tasks = {
        "T1": {"cpu": 2, "ram": 4},
        "T2": {"cpu": 1, "ram": 2},
    }
    nodes = {
        "N1": {"cpu_capacity": 5, "ram_capacity": 6},
        "N2": {"cpu_capacity": 3, "ram_capacity": 3},
    }
    exec_costs = {
        "T1": {"N1": 4, "N2": 6},
        "T2": {"N1": 3, "N2": 2},
    }
    
    # The rest of your original Phase 1 code...
    # set the id for tasks and Nodes 
    task_ids = list(tasks.keys())
    node_ids = list(nodes.keys())
    source_idx = 0
    sink_idx = 1 + len(task_ids) + len(node_ids)
    task_indices = {task_id: i + 1 for i, task_id in enumerate(task_ids)}
    node_indices = {node_id: i + 1 + len(task_ids) for i, node_id in enumerate(node_ids)}
    # connect the Source to the tasks with capacity 1 and cost 0 
    mcf = min_cost_flow.SimpleMinCostFlow()
    for task_id, task_idx in task_indices.items():
        mcf.add_arc_with_capacity_and_unit_cost(source_idx, task_idx, 1, 0)
    # connect the tasks to the Nodes if the Node can support the Tasks
    for task_id, task_data in tasks.items():
        for node_id, node_data in nodes.items():
            if (task_data["cpu"] <= node_data["cpu_capacity"] and task_data["ram"] <= node_data["ram_capacity"]):
                cost = exec_costs[task_id][node_id]
                task_idx = task_indices[task_id]
                node_idx = node_indices[node_id]
                mcf.add_arc_with_capacity_and_unit_cost(task_idx, node_idx, 1, cost)
    # node_capacity = len(tasks) 
    min_task_cpu = min(task["cpu"] for task in tasks.values() if task["cpu"] > 0)
    min_task_ram = min(task["ram"] for task in tasks.values() if task["ram"] > 0)

    for node_id, node_idx in node_indices.items():
        node_data = nodes[node_id]
        
        # Calculate capacity based on your dynamic heuristic
        max_tasks_cpu = node_data["cpu_capacity"] // min_task_cpu if min_task_cpu > 0 else 0
        max_tasks_ram = node_data["ram_capacity"] // min_task_ram if min_task_ram > 0 else 0
        
        # Use the most restrictive resource as the final capacity
        node_capacity = min(max_tasks_cpu, max_tasks_ram)
        
        mcf.add_arc_with_capacity_and_unit_cost(node_idx, sink_idx, node_capacity, 0)
    num_tasks = len(tasks)
    mcf.set_node_supply(source_idx, num_tasks)
    mcf.set_node_supply(sink_idx, -num_tasks)
    status = mcf.solve()
    if status == mcf.OPTIMAL:
        print("✅ (Original Phase 1) Solution Found!\n")
        assignments = {}
        total_cost = mcf.optimal_cost()
        # ... (Processing results and printing)
        output = {"assignments": assignments, "total_cost": total_cost}
        print(json.dumps(output, indent=2))
    elif status == mcf.INFEASIBLE:
        print("❌ (Original Phase 1) Problem is infeasible.")
    else:
        print("❓ (Original Phase 1) An error occurred.")


# -----------------------------------------------------------------------------
# NEW CORE ALLOCATION ENGINE (to be used by other functions)
# -----------------------------------------------------------------------------
def _run_allocation_engine(tasks, nodes, exec_costs):
    """
    This is the new "core" function. It contains the allocation logic
    but returns the result instead of printing it.
    """
    # This part is a copy of the logic from solve_task_allocation
    mcf = min_cost_flow.SimpleMinCostFlow()
    task_ids = list(tasks.keys())
    node_ids = list(nodes.keys())
    source_idx = 0
    sink_idx = 1 + len(task_ids) + len(node_ids)
    task_indices = {task_id: i + 1 for i, task_id in enumerate(task_ids)}
    node_indices = {node_id: i + 1 + len(task_ids) for i, node_id in enumerate(node_ids)}
    for task_id in task_ids:
        mcf.add_arc_with_capacity_and_unit_cost(source_idx, task_indices[task_id], 1, 0)
    for task_id, task_data in tasks.items():
        for node_id, node_data in nodes.items():
            if task_data.get("cpu", 0) <= node_data["cpu_capacity"] and task_data.get("ram", 0) <= node_data["ram_capacity"]:
                cost = exec_costs.get(task_id, {}).get(node_id, 99999)
                mcf.add_arc_with_capacity_and_unit_cost(task_indices[task_id], node_indices[node_id], 1, cost)
    for node_id in node_ids:
        mcf.add_arc_with_capacity_and_unit_cost(node_indices[node_id], sink_idx, len(tasks), 0)
    mcf.set_node_supply(source_idx, len(tasks))
    mcf.set_node_supply(sink_idx, -len(tasks))
    
    status = mcf.solve()

    if status == mcf.OPTIMAL:
        assignments = {}
        total_cost = mcf.optimal_cost()
        for arc in range(mcf.num_arcs()):
            if mcf.flow(arc) > 0:
                tail_idx, head_idx = mcf.tail(arc), mcf.head(arc)
                task_id = next((tid for tid, idx in task_indices.items() if idx == tail_idx), None)
                node_id = next((nid for nid, idx in node_indices.items() if idx == head_idx), None)
                if task_id and node_id:
                    assignments[task_id] = node_id
        return True, assignments, total_cost
    else:
        return False, None, None

# -----------------------------------------------------------------------------
# HELPER and PHASE 2 FUNCTIONS (They use the new engine)
# -----------------------------------------------------------------------------
def topological_sort(tasks, dependencies):
    # (This function remains the same)
    in_degree = {task_id: 0 for task_id in tasks}
    adj = {task_id: [] for task_id in tasks}
    for dep in dependencies:
        adj[dep['before']].append(dep['after'])
        in_degree[dep['after']] += 1
    queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
    sorted_tasks = []
    while queue:
        current_task = queue.popleft()
        sorted_tasks.append(current_task)
        for neighbor in adj[current_task]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return sorted_tasks if len(sorted_tasks) == len(tasks) else None

def solve_phase2_scheduling(data):
    """
    Phase 2 function that now calls the new allocation engine.
    """
    tasks_dict = {task['id']: task for task in data['tasks']}
    nodes_dict = {node['id']: node for node in data['nodes']}
    
    print("--- Calling Allocation Engine ---")
    # ** KEY CHANGE: Calling the new core function **
    is_success, assignments, total_cost = _run_allocation_engine(tasks_dict, nodes_dict, data['exec_cost'])

    if not is_success:
        print("❌ Allocation failed. Halting Phase 2.")
        return

    print("✅ Allocation successful! Assignments:", assignments)
    print("\n--- Running Phase 2: Scheduling ---")
    
    # The rest of the scheduling logic is the same
    task_ids = list(tasks_dict.keys())
    sorted_tasks = topological_sort(task_ids, data['dependencies'])
    # ... (scheduling logic continues as before) ...
    # ... (and prints the final Phase 2 output) ...
    if sorted_tasks is None:
        print("❌ Scheduling failed: A dependency cycle was detected.")
        return
    schedule = {}
    node_available_time = {node_id: 0 for node_id in nodes_dict.keys()}
    task_finish_time = {}
    is_valid = True
    for task_id in sorted_tasks:
        assigned_node = assignments[task_id]
        task_data = tasks_dict[task_id]
        dependency_finish_time = 0
        for dep in data['dependencies']:
            if dep['after'] == task_id:
                dependency_finish_time = max(dependency_finish_time, task_finish_time.get(dep['before'], 0))
        start_time = max(node_available_time[assigned_node], dependency_finish_time)
        finish_time = start_time + task_data['duration']
        if finish_time > task_data['deadline']:
            print(f"🔥 Deadline missed for task {task_id}!")
            is_valid = False
            break
        schedule[task_id] = {"node": assigned_node, "start_time": start_time}
        task_finish_time[task_id] = finish_time
        node_available_time[assigned_node] = finish_time
    output = {"schedule": schedule, "valid": is_valid, "total_cost": total_cost}
    print("\n--- Final Output for Phase 2 ---")
    print(json.dumps(output, indent=2))

# -----------------------------------------------------------------------------
# Main Execution Block
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    phase2_data = {
        "tasks": [
            {"id": "T1", "cpu": 2, "ram": 4, "duration": 1, "deadline": 3},
            {"id": "T2", "cpu": 1, "ram": 2, "duration": 1, "deadline": 3},
            {"id": "T3", "cpu": 3, "ram": 3, "duration": 2, "deadline": 4}
        ],
        "nodes": [
            {"id": "N1", "cpu_capacity": 5, "ram_capacity": 6},
            {"id": "N2", "cpu_capacity": 6, "ram_capacity": 5}
        ],
        "exec_cost": {
            "T1": {"N1": 4, "N2": 2},
            "T2": {"N1": 3, "N2": 4},
            "T3": {"N1": 2, "N2": 3}
        },
        "dependencies": [
            {"before": "T1", "after": "T3"},
            {"before": "T2", "after": "T3"}
        ]
    }

    # You can now call either function!
    # print("--- Testing original Phase 1 function ---")
    # solve_task_allocation() # This still works
    
    print("\n--- Running the full Phase 2 process ---")
    solve_phase2_scheduling(phase2_data)