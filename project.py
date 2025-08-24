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