import json
from collections import deque
from ortools.graph.python import min_cost_flow

# -----------------------------------------------------------------------------
# PHASE 1: ALLOCATION FUNCTION (WITH THE FIX)
# -----------------------------------------------------------------------------
def run_phase1_allocation(tasks, nodes, exec_costs, node_capacity_per_time):
    """
    Solves the allocation problem, now with a pre-check to prevent
    assigning tasks to nodes that can never support their resource needs.
    """
    print("--- Running Phase 1: Smart Task Allocation ---")
    task_ids = list(tasks.keys())
    node_ids = list(nodes.keys())
    
    # ... (rest of the setup code is the same) ...
    source_idx = 0
    sink_idx = 1 + len(task_ids) + len(node_ids)
    task_indices = {task_id: i + 1 for i, task_id in enumerate(task_ids)}
    node_indices = {node_id: i + 1 + len(task_ids) for i, node_id in enumerate(node_ids)}

    mcf = min_cost_flow.SimpleMinCostFlow()

    # Arcs from Source to Tasks
    for task_id, task_idx in task_indices.items():
        mcf.add_arc_with_capacity_and_unit_cost(source_idx, task_idx, 1, 0)

    # Arcs from Tasks to Nodes
    for task_id, task_data in tasks.items():
        for node_id, node_data in nodes.items():
            
            # --- THIS IS THE NEW, SMARTER CHECK ---
            # Find the maximum CPU this node ever has available at any single time slot
            max_node_instant_cpu = max(node_capacity_per_time[node_id].values()) if node_id in node_capacity_per_time else 0
            
            # The original checks plus our new, smarter condition
            if (task_data["cpu"] <= node_data["cpu_capacity"] and
                task_data["ram"] <= node_data["ram_capacity"] and
                task_data["cpu"] <= max_node_instant_cpu): # <-- THE FIX IS HERE!
                
                cost = exec_costs[task_id][node_id]
                task_idx = task_indices[task_id]
                node_idx = node_indices[node_id]
                mcf.add_arc_with_capacity_and_unit_cost(task_idx, node_idx, 1, cost)

    # ... (The rest of the Phase 1 function is the same) ...
    min_task_cpu = min(t["cpu"] for t in tasks.values() if t["cpu"] > 0)
    min_task_ram = min(t["ram"] for t in tasks.values() if t["ram"] > 0)
    
    for node_id, node_idx in node_indices.items():
        node_data = nodes[node_id]
        max_tasks_cpu = node_data["cpu_capacity"] // min_task_cpu if min_task_cpu > 0 else 0
        max_tasks_ram = node_data["ram_capacity"] // min_task_ram if min_task_ram > 0 else 0
        node_capacity = min(max_tasks_cpu, max_tasks_ram)
        mcf.add_arc_with_capacity_and_unit_cost(node_idx, sink_idx, node_capacity, 0)

    num_tasks = len(tasks)
    mcf.set_node_supply(source_idx, num_tasks)
    mcf.set_node_supply(sink_idx, -num_tasks)

    status = mcf.solve()

    if status == mcf.OPTIMAL:
        print("✅ Phase 1 successful!")
        assignments = {}
        total_cost = mcf.optimal_cost() 
        for arc in range(mcf.num_arcs()):
            if mcf.flow(arc) > 0:
                tail, head = mcf.tail(arc), mcf.head(arc)
                task_id = next((tid for tid, idx in task_indices.items() if idx == tail), None)
                node_id = next((nid for nid, idx in node_indices.items() if idx == head), None)
                if task_id and node_id:
                    assignments[task_id] = node_id
        return assignments , total_cost
    else:
        print("❌ Phase 1 failed. No feasible assignment found.")
        return None , None

# -----------------------------------------------------------------------------
# PHASE 2: ADVANCED SCHEDULING FUNCTIONS (Final Version)
# -----------------------------------------------------------------------------
def topological_sort(tasks, dependencies):
    """Performs a topological sort on tasks."""
    in_degree = {task_id: 0 for task_id in tasks}
    adj_list = {task_id: [] for task_id in tasks}
    for dep in dependencies:
        adj_list[dep["before"]].append(dep["after"])
        in_degree[dep["after"]] += 1
    queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
    sorted_order = []
    while queue:
        current_task = queue.popleft()
        sorted_order.append(current_task)
        for neighbor in adj_list[current_task]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if len(sorted_order) == len(tasks):
        return sorted_order
    return None

def find_earliest_slot(node_timeline, node_capacity_per_time, task_duration, task_cpu, time_slots):
    """
    Finds the earliest time slot where a task can fit for its entire duration,
    respecting the explicit time_slots list.
    """
    for t_index, t_value in enumerate(time_slots):
        can_fit = True
        for i in range(task_duration):
            if (t_index + i) >= len(time_slots):
                can_fit = False
                break
            
            current_time_slot = time_slots[t_index + i]
            time_slot_key = str(current_time_slot)

            if node_timeline[current_time_slot] + task_cpu > node_capacity_per_time.get(time_slot_key, 0):
                can_fit = False
                break
        
        if can_fit:
            return t_value
            
    return -1

def create_final_schedule_phase2(assignments, sorted_tasks, tasks_data, nodes_data, node_capacity_per_time, time_slots):
    """
    Creates a final schedule that uses all Phase 2 inputs, including time_slots.
    """
    print("\n--- Running FINAL Phase 2: Parallel-Aware Scheduling ---")
    
    max_time_val = max(time_slots) if time_slots else -1
    node_timelines = {node_id: [0] * (max_time_val + 1) for node_id in nodes_data}
    
    schedule = {}
    
    print("Building schedule in this order:", sorted_tasks)
    for task_id in sorted_tasks:
        task_info = tasks_data[task_id]
        assigned_node = assignments[task_id]
        
        start_time = find_earliest_slot(
            node_timelines[assigned_node],
            node_capacity_per_time[assigned_node],
            task_info["duration"],
            task_info["cpu"],
            time_slots
        )
        
        if start_time == -1:
            print(f"❌ SCHEDULING FAILED: No available slot found for task '{task_id}'.")
            return None, False
            
        finish_time = start_time + task_info["duration"]
        
        if finish_time > task_info["deadline"]:
            print(f"❌ SCHEDULING FAILED: Task '{task_id}' misses its deadline.")
            return None, False

        schedule[task_id] = {
            "node": assigned_node,
            "start_time": start_time,
            "finish_time": finish_time
        }
        
        for i in range(task_info["duration"]):
            node_timelines[assigned_node][start_time + i] += task_info["cpu"]
            
    print("✅ Final Scheduling Successful!")
    return schedule, True

# -----------------------------------------------------------------------------
# MAIN EXECUTION BLOCK
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # --- Using your failing input data ---
    tasks_with_time = {
        "T1": {"cpu": 2, "ram": 4, "duration": 1, "deadline": 3},
        "T2": {"cpu": 1, "ram": 2, "duration": 1, "deadline": 3},
        "T3": {"cpu": 3, "ram": 3, "duration": 2, "deadline": 4},
    }
    nodes = {
        "N1": {"cpu_capacity": 5, "ram_capacity": 6},
        "N2": {"cpu_capacity": 6, "ram_capacity": 5},
    }
    exec_costs = {
        "T1": {"N1": 4, "N2": 2},
        "T2": {"N1": 4, "N2": 4},
        "T3": {"N1": 2, "N2": 3},
    }
    dependencies = [
        {"before": "T1", "after": "T3"},
        {"before": "T2", "after": "T3"}
    ]
    time_slots = [0, 1, 2, 3]
    node_capacity_per_time = {
       "N1": {"0": 2, "1": 2, "2": 2, "3": 2},
       "N2": {"0": 3, "1": 3, "2": 2, "3": 2}
    }


    # tasks_with_time = {
    # "T1": {"cpu": 2, "ram": 4, "duration": 1, "deadline": 3},
    # "T2": {"cpu": 1, "ram": 2, "duration": 1, "deadline": 3},
    # "T3": {"cpu": 3, "ram": 3, "duration": 2, "deadline": 4},
    # }
    # nodes = {
    #     "N1": {"cpu_capacity": 5, "ram_capacity": 6},
    #     "N2": {"cpu_capacity": 6, "ram_capacity": 5},
    # }
    # exec_costs = {
    #     "T1": {"N1": 4, "N2": 2},
    #     "T2": {"N1": 4, "N2": 4},
    #     "T3": {"N1": 9, "N2": 3}, # Increased N1 cost to ensure T3 goes to N2
    # }
    # dependencies = [
    #     {"before": "T1", "after": "T3"},
    #     {"before": "T2", "after": "T3"}
    # ]
    # time_slots = [0, 1, 2, 3]

    # # --- THE ONLY KEY CHANGE IS HERE ---
    # node_capacity_per_time = {
    #    "N1": {"0": 2, "1": 2, "2": 2, "3": 2},
    #    # N2 now has enough capacity for T3's entire duration
    #    "N2": {"0": 3, "1": 3, "2": 3, "3": 3}
    # }

    # --- Run the full workflow ---
    # Note that we now pass `node_capacity_per_time` to Phase 1
    assignments , total_cost = run_phase1_allocation(tasks_with_time, nodes, exec_costs, node_capacity_per_time)

    if assignments:
        print("\nPhase 1 Assignments:", json.dumps(assignments, indent=2))
        
        sorted_order = topological_sort(tasks_with_time, dependencies)
        if sorted_order:
            final_schedule, is_valid = create_final_schedule_phase2(
                assignments,
                sorted_order,
                tasks_with_time,
                nodes,
                node_capacity_per_time,
                time_slots
            )
            if is_valid:
                final_output = {
                    "schedule": final_schedule,
                    "total_assignment_cost": total_cost
                }
                print("\n--- FINAL VALID SCHEDULE ---")
                print(json.dumps(final_output, indent=2))
        else:
            print("❌ Phase 2 failed: A cycle was detected in dependencies.")