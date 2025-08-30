from ortools.graph.python import min_cost_flow

def solve_task_allocation():
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
    
    task_ids = list(tasks.keys())
    node_ids = list(nodes.keys())
    
    source_idx = 0
    sink_idx = 1 + len(task_ids) + len(node_ids)
    task_indices = {task_id: i + 1 for i, task_id in enumerate(task_ids)}
    node_indices = {node_id: i + 1 + len(task_ids) for i, node_id in enumerate(node_ids)}
    
    mcf = min_cost_flow.SimpleMinCostFlow()

    
    for task_id, task_idx in task_indices.items():
        mcf.add_arc_with_capacity_and_unit_cost(source_idx, task_idx, 1, 0)

    for task_id, task_data in tasks.items():
        for node_id, node_data in nodes.items():
            if (task_data["cpu"] <= node_data["cpu_capacity"] and
                task_data["ram"] <= node_data["ram_capacity"]):
                
                cost = exec_costs[task_id][node_id]
                task_idx = task_indices[task_id]
                node_idx = node_indices[node_id]
                mcf.add_arc_with_capacity_and_unit_cost(task_idx, node_idx, 1, cost)

    node_capacity = len(tasks) 
    for node_id, node_idx in node_indices.items():
        mcf.add_arc_with_capacity_and_unit_cost(node_idx, sink_idx, node_capacity, 0)

    num_tasks = len(tasks)
    mcf.set_node_supply(source_idx, num_tasks)
    mcf.set_node_supply(sink_idx, -num_tasks)

    status = mcf.solve()

    if status == mcf.OPTIMAL:
        print("✅ Solution Found!\n")
        
        assignments = {}
        total_cost = mcf.optimal_cost()

        for arc in range(mcf.num_arcs()):
            if mcf.flow(arc) > 0:
                head = mcf.head(arc)
                tail = mcf.tail(arc)
                
                task_id = next((tid for tid, idx in task_indices.items() if idx == tail), None)
                node_id = next((nid for nid, idx in node_indices.items() if idx == head), None)

                if task_id and node_id:
                    assignments[task_id] = node_id
                    print(f"   Assignment: {task_id} -> {node_id} (Cost: {mcf.unit_cost(arc)})")
        
        print("\n--- Final Output (JSON-like) ---")
        output = {
            "assignments": assignments,
            "total_cost": total_cost,
        }
        import json
        print(json.dumps(output, indent=2))
        
    elif status == mcf.INFEASIBLE:
        print("Problem is infeasible. Not all tasks can be assigned.")
    else:
        print("An error occurred.")


solve_task_allocation()


# ----------------------    finish phase1   ----------------------------

# ----------------------    start phase2   ----------------------------

# First, install the library if you haven't:
# pip install ortools

from ortools.graph.python import min_cost_flow
from collections import deque

def topological_sort(tasks, dependencies):
    """
    Performs a topological sort on the tasks based on dependencies.
    Returns a sorted list of task IDs or None if a cycle is detected.
    """
    in_degree = {task_id: 0 for task_id in tasks}
    adj = {task_id: [] for task_id in tasks}

    for dep in dependencies:
        # dep['before'] -> dep['after']
        before_task = dep['before']
        after_task = dep['after']
        adj[before_task].append(after_task)
        in_degree[after_task] += 1

    queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
    sorted_tasks = []

    while queue:
        current_task = queue.popleft()
        sorted_tasks.append(current_task)

        for neighbor in adj[current_task]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_tasks) == len(tasks):
        return sorted_tasks
    else:
        return None  # Cycle detected

def solve_phase2_scheduling(data):
    """
    Solves task allocation and scheduling for Phase 2.
    First, it allocates tasks using MCMF (Phase 1 logic).
    Then, it creates a valid schedule respecting dependencies and deadlines.
    """
    tasks = {task['id']: task for task in data['tasks']}
    nodes = {node['id']: node for node in data['nodes']}
    exec_costs = data['exec_cost']
    dependencies = data['dependencies']

    # --- STAGE 1: ALLOCATION (Similar to Phase 1) ---
    mcf = min_cost_flow.SimpleMinCostFlow()

    task_ids = list(tasks.keys())
    node_ids = list(nodes.keys())

    source_idx = 0
    sink_idx = len(task_ids) + len(node_ids) + 1
    task_indices = {task_id: i + 1 for i, task_id in enumerate(task_ids)}
    node_indices = {node_id: i + 1 + len(task_ids) for i, node_id in enumerate(node_ids)}

    for task_id in task_ids:
        mcf.add_arc_with_capacity_and_unit_cost(source_idx, task_indices[task_id], 1, 0)

    for task_id, task_data in tasks.items():
        for node_id, node_data in nodes.items():
            if task_data.get("cpu", 0) <= node_data["cpu_capacity"] and task_data.get("ram", 0) <= node_data["ram_capacity"]:
                cost = exec_costs.get(task_id, {}).get(node_id, 99999) # High cost if not specified
                mcf.add_arc_with_capacity_and_unit_cost(task_indices[task_id], node_indices[node_id], 1, cost)
    
    for node_id in node_ids:
        mcf.add_arc_with_capacity_and_unit_cost(node_indices[node_id], sink_idx, len(tasks), 0)

    mcf.set_node_supply(source_idx, len(tasks))
    mcf.set_node_supply(sink_idx, -len(tasks))

    status = mcf.solve()

    if status != mcf.OPTIMAL:
        print("❌ Allocation failed or is infeasible.")
        return

    assignments = {}
    total_cost = mcf.optimal_cost()
    for arc in range(mcf.num_arcs()):
        if mcf.flow(arc) > 0:
            tail_idx = mcf.tail(arc)
            head_idx = mcf.head(arc)
            task_id = next((tid for tid, idx in task_indices.items() if idx == tail_idx), None)
            node_id = next((nid for nid, idx in node_indices.items() if idx == head_idx), None)
            if task_id and node_id:
                assignments[task_id] = node_id

    # --- STAGE 2: SCHEDULING ---
    sorted_tasks = topological_sort(task_ids, dependencies)
    if sorted_tasks is None:
        print("❌ Scheduling failed: A dependency cycle was detected.")
        return

    schedule = {}
    node_available_time = {node_id: 0 for node_id in node_ids}
    task_finish_time = {task_id: 0 for task_id in task_ids}
    is_valid = True

    for task_id in sorted_tasks:
        assigned_node = assignments[task_id]
        task_data = tasks[task_id]

        # Determine earliest start time based on dependencies
        dependency_finish_time = 0
        for dep in dependencies:
            if dep['after'] == task_id:
                dependency_finish_time = max(dependency_finish_time, task_finish_time[dep['before']])
        
        start_time = max(node_available_time[assigned_node], dependency_finish_time)
        finish_time = start_time + task_data['duration']

        # Check deadline
        if finish_time > task_data['deadline']:
            print(f"🔥 Deadline missed for task {task_id}! (Finishes at {finish_time}, deadline is {task_data['deadline']})")
            is_valid = False
            break

        # Update schedule and timelines
        schedule[task_id] = {"node": assigned_node, "start_time": start_time}
        task_finish_time[task_id] = finish_time
        node_available_time[assigned_node] = finish_time

    # --- Final Output ---
    output = {
        "schedule": schedule,
        "valid": is_valid,
        "total_cost": total_cost
    }
    
    import json
    print("\n--- Final Output for Phase 2 ---")
    print(json.dumps(output, indent=2))


# --- Example Input Data from PDF (Pages 13-14) ---
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

solve_phase2_scheduling(phase2_data)

# https://t.me/proxy?server=87.248.132.44&port=200&secret=ee0000f00f0f775555fffffff5006e2e69646F776E6C6F61642E77696E646F77737570646174652E636F6D