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


# This new function will be the entry point for Phase 3
def run_phase3_dynamic_reallocation(initial_schedule, initial_data, events):
    """
    Handles a list of runtime events to update the schedule dynamically.
    """
    print("\n--- Running Phase 3: Dynamic Reallocation ---")
    
    # We start with the valid schedule from Phase 2
    current_schedule = initial_schedule.copy()
    
    # We need a mutable copy of the original data to work with
    tasks_data = initial_data["tasks"].copy()
    nodes_data = initial_data["nodes"].copy()
    
    for event in events:
        if event["type"] == "node_failure":
            failed_node = event["node_id"]
            failure_time = event["time"]
            
            print(f"\n🚨 EVENT: Node '{failed_node}' failed at time {failure_time}!")
            
            # --- Step 1: Identify "Homeless" Tasks ---
            homeless_tasks_ids = []
            for task_id, schedule_info in current_schedule.items():
                if (schedule_info["node"] == failed_node and 
                    schedule_info["start_time"] >= failure_time):
                    homeless_tasks_ids.append(task_id)
            
            if not homeless_tasks_ids:
                print("No running or future tasks were on the failed node. Schedule is unaffected.")
                continue

            print("Homeless tasks that need reallocation:", homeless_tasks_ids)

            # Remove the failed node from our active nodes list
            del nodes_data[failed_node]
            if not nodes_data:
                print("❌ CRITICAL FAILURE: No remaining nodes available.")
                return None, {"failed_tasks": homeless_tasks_ids}

            # --- Step 2: Re-Allocate (Mini Phase 1) ---
            homeless_tasks_data = {tid: tasks_data[tid] for tid in homeless_tasks_ids}
            new_assignments, _ = run_phase1_allocation(
                homeless_tasks_data,
                nodes_data,
                initial_data["exec_costs"],
                initial_data["node_capacity_per_time"]
            )

            if not new_assignments:
                print("❌ Re-allocation failed. No new home found for homeless tasks.")
                return None, {"failed_tasks": homeless_tasks_ids}
            
            print("✅ Re-allocation successful:", new_assignments)
            
            # --- Step 3: Re-Schedule (Mini Phase 2) ---
            updated_schedule, result = attempt_to_reschedule(
                current_schedule,
                homeless_tasks_ids,
                new_assignments,
                initial_data
            )
            
            if not result["is_valid"]:
                print("❌ System recovery failed during re-scheduling.")
                return None, result
            else:
                print("✅ System recovery successful! Schedule has been updated.")
                current_schedule = updated_schedule

        elif event["type"] == "new_task":
            # Logic for handling a new task would go here
            print(f"\nEVENT: New task '{event['task']['id']}' arrived. (Handler not implemented yet).")
    
    return current_schedule, {"is_valid": True, "failed_tasks": []}


def attempt_to_reschedule(current_schedule, homeless_tasks_ids, new_assignments, initial_data):
    """
    Tries to fit the newly re-allocated tasks into the existing schedule.
    """
    # 1. Create a new schedule containing only the "healthy" tasks
    healthy_schedule = {
        task_id: schedule_info 
        for task_id, schedule_info in current_schedule.items() 
        if task_id not in homeless_tasks_ids
    }
    
    remaining_nodes = {nid: data for nid, data in initial_data["nodes"].items() if nid in new_assignments.values()}

    # 2. Rebuild the timelines based on the healthy tasks
    max_time_val = max(initial_data["time_slots"]) if initial_data["time_slots"] else 0
    node_timelines = {node_id: [0] * (max_time_val + 1) for node_id in remaining_nodes}

    for task_id, schedule_info in healthy_schedule.items():
        # Ensure the node for the healthy task still exists
        if schedule_info["node"] in node_timelines:
            node_id = schedule_info["node"]
            start = schedule_info["start_time"]
            duration = initial_data["tasks"][task_id]["duration"]
            cpu_need = initial_data["tasks"][task_id]["cpu"]
            for i in range(duration):
                if start + i < len(node_timelines[node_id]):
                    node_timelines[node_id][start + i] += cpu_need

    # 3. Try to schedule the homeless tasks
    # Inside attempt_to_reschedule...
    # 3. Try to schedule the homeless tasks
    
    # --- THIS IS THE FIX ---
    # Filter the dependencies to only include those *between* the homeless tasks.
    homeless_dependencies = [
        dep for dep in initial_data["dependencies"]
        if dep["before"] in homeless_tasks_ids and dep["after"] in homeless_tasks_ids
    ]
    
    homeless_topo_sort = topological_sort(
        {tid: initial_data["tasks"][tid] for tid in homeless_tasks_ids},
        homeless_dependencies # Use the new, filtered list
    )
    # --- END OF FIX ---
    
    updated_schedule = healthy_schedule.copy()
    failed_to_reschedule = []

    for task_id in homeless_topo_sort:
        task_info = initial_data["tasks"][task_id]
        assigned_node = new_assignments[task_id]
        
        start_time = find_earliest_slot(
            node_timelines[assigned_node],
            initial_data["node_capacity_per_time"][assigned_node],
            task_info["duration"],
            task_info["cpu"],
            initial_data["time_slots"]
        )
        
        finish_time = start_time + task_info["duration"] if start_time != -1 else -1

        if start_time == -1 or finish_time > task_info["deadline"]:
            failed_to_reschedule.append(task_id)
            continue

        updated_schedule[task_id] = {"node": assigned_node, "start_time": start_time, "finish_time": finish_time}
        
        for i in range(task_info["duration"]):
            node_timelines[assigned_node][start_time + i] += task_info["cpu"]

    if failed_to_reschedule:
        return None, {"is_valid": False, "failed_tasks": failed_to_reschedule}

    return updated_schedule, {"is_valid": True, "failed_tasks": []}

def run_phase4_local_scheduler(assigned_tasks, node_id, node_data, node_capacity_per_time, time_slots):
    """
    Schedules tasks assigned to a single node using a smarter,
    Earliest Deadline First (EDF) greedy heuristic.
    """
    print(f"\n--- Running Phase 4: Local Scheduling on Node '{node_id}' ---")
    
    # Sort the assigned tasks by their deadline (Earliest Deadline First)
    tasks_to_schedule_ids = sorted(
        assigned_tasks.keys(),
        key=lambda tid: assigned_tasks[tid]["deadline"]
    )
    
    print(f"Scheduling tasks in EDF order: {tasks_to_schedule_ids}")

    # Use the same advanced scheduling logic from Phase 2
    max_time_val = max(time_slots) if time_slots else 0
    node_timeline = [0] * (max_time_val + 1)
    
    local_schedule = {}
    
    for task_id in tasks_to_schedule_ids:
        task_info = assigned_tasks[task_id]
        
        start_time = find_earliest_slot(
            node_timeline,
            node_capacity_per_time[node_id],
            task_info["duration"],
            task_info["cpu"],
            time_slots
        )
        
        finish_time = start_time + task_info["duration"] if start_time != -1 else -1

        if start_time == -1 or finish_time > task_info["deadline"]:
            print(f"❌ Local scheduling FAILED for task '{task_id}'.")
            local_schedule[task_id] = {"status": "failed", "reason": "No valid slot found"}
            continue

        local_schedule[task_id] = {
            "status": "success",
            "start_time": start_time,
            "finish_time": finish_time
        }
        
        for i in range(task_info["duration"]):
            node_timeline[start_time + i] += task_info["cpu"]
            
    print(f"✅ Local scheduling for Node '{node_id}' complete.")
    return local_schedule

# --- How you would integrate this into your main block ---
#
# if assignments:
#     # ... after Phase 1 runs ...
#     final_system_schedule = {}
#
#     # Group tasks by the node they were assigned to
#     tasks_per_node = {node_id: {} for node_id in nodes}
#     for task_id, node_id in assignments.items():
#         tasks_per_node[node_id][task_id] = tasks_with_time[task_id]
#
#     # Run the local scheduler for each node
#     for node_id, assigned_tasks in tasks_per_node.items():
#         if not assigned_tasks:
#             continue
#         
#         node_schedule = run_phase4_local_scheduler(
#             assigned_tasks,
#             node_id,
#             nodes[node_id],
#             node_capacity_per_time,
#             time_slots
#         )
#         final_system_schedule[node_id] = node_schedule
#
#     print("\n--- FINAL SYSTEM SCHEDULE (Phase 4) ---")
#     print(json.dumps(final_system_schedule, indent=2))

# You would call this from your main block after getting a valid Phase 2 schedule
# Example:
# if is_valid:
#     events = [
#         {"type": "node_failure", "node_id": "N2", "time": 1}
#     ]
#     initial_data = { "tasks": tasks_with_time, "nodes": nodes, ... }
#     final_schedule, result = run_phase3_dynamic_reallocation(final_schedule, initial_data, events)
#     if final_schedule:
#        # print the final result


# -----------------------------------------------------------------------------
# MAIN EXECUTION BLOCK
# -----------------------------------------------------------------------------

# if __name__ == "__main__":
    # --- Using your failing input data ---
    # tasks_with_time = {
    #     "T1": {"cpu": 2, "ram": 4, "duration": 1, "deadline": 3},
    #     "T2": {"cpu": 1, "ram": 2, "duration": 1, "deadline": 3},
    #     "T3": {"cpu": 3, "ram": 3, "duration": 2, "deadline": 4},
    # }
    # nodes = {
    #     "N1": {"cpu_capacity": 5, "ram_capacity": 6},
    #     "N2": {"cpu_capacity": 6, "ram_capacity": 5},
    # }
    # exec_costs = {
    #     "T1": {"N1": 4, "N2": 2},
    #     "T2": {"N1": 4, "N2": 4},
    #     "T3": {"N1": 2, "N2": 3},
    # }
    # dependencies = [
    #     {"before": "T1", "after": "T3"},
    #     {"before": "T2", "after": "T3"}
    # ]
    # time_slots = [0, 1, 2, 3]
    # node_capacity_per_time = {
    #    "N1": {"0": 2, "1": 2, "2": 2, "3": 2},
    #    "N2": {"0": 3, "1": 3, "2": 2, "3": 2}
    # }


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
    # assignments , total_cost = run_phase1_allocation(tasks_with_time, nodes, exec_costs, node_capacity_per_time)

    # if assignments:
    #     print("\nPhase 1 Assignments:", json.dumps(assignments, indent=2))
        
    #     sorted_order = topological_sort(tasks_with_time, dependencies)
    #     if sorted_order:
    #         final_schedule, is_valid = create_final_schedule_phase2(
    #             assignments,
    #             sorted_order,
    #             tasks_with_time,
    #             nodes,
    #             node_capacity_per_time,
    #             time_slots
    #         )
    #         if is_valid:
    #             final_output = {
    #                 "schedule": final_schedule,
    #                 "total_assignment_cost": total_cost
    #             }
    #             print("\n--- FINAL VALID SCHEDULE ---")
    #             print(json.dumps(final_output, indent=2))
    #     else:
    #         print("❌ Phase 2 failed: A cycle was detected in dependencies.")


# -----------------------------------------------------------------------------
# MAIN EXECUTION BLOCK - COPY AND PASTE THIS AT THE END OF YOUR FILE
# -----------------------------------------------------------------------------
# if __name__ == "__main__":
#     # --- 1. Define the Initial State of the System ---
#     initial_data = {
#         "tasks": {
#             "T1": {"cpu": 2, "ram": 4, "duration": 1, "deadline": 3},
#             "T2": {"cpu": 1, "ram": 2, "duration": 1, "deadline": 3},
#             "T3": {"cpu": 3, "ram": 3, "duration": 2, "deadline": 4},
#         },
#         "nodes": {
#             "N1": {"cpu_capacity": 5, "ram_capacity": 6},
#             "N2": {"cpu_capacity": 6, "ram_capacity": 5},
#         },
#         "exec_costs": {
#             "T1": {"N1": 4, "N2": 2},
#             "T2": {"N1": 4, "N2": 4},
#             "T3": {"N1": 9, "N2": 3},
#         },
#         "dependencies": [
#             {"before": "T1", "after": "T3"},
#             {"before": "T2", "after": "T3"}
#         ],
#         "time_slots": [0, 1, 2, 3, 4],
#         "node_capacity_per_time": {
#            "N1": {"0": 5, "1": 5, "2": 5, "3": 5, "4": 5},
#            "N2": {"0": 3, "1": 3, "2": 3, "3": 3, "4": 3}
#         }
#     }

#     # --- 2. Run Phases 1 and 2 to get the initial, valid schedule ---
#     assignments, total_cost = run_phase1_allocation(
#         initial_data["tasks"], 
#         initial_data["nodes"], 
#         initial_data["exec_costs"], 
#         initial_data["node_capacity_per_time"]
#     )
    
#     initial_schedule = None
#     if assignments:
#         print("\nInitial Assignments:", json.dumps(assignments, indent=2))
#         sorted_order = topological_sort(initial_data["tasks"], initial_data["dependencies"])
        
#         # Inside the main block...
#         if sorted_order:
#             initial_schedule, is_valid = create_final_schedule_phase2(
#                 assignments,
#                 sorted_order,
#                 initial_data["tasks"],
#                 initial_data["nodes"],
#                 initial_data["node_capacity_per_time"],
#                 initial_data["time_slots"]
#             )
#             if is_valid:
#                 print("\n--- Initial Valid Schedule Created ---")
#                 print(json.dumps({"schedule": initial_schedule, "cost": total_cost}, indent=2))

#     # --- 3. If the initial schedule is valid, introduce a runtime event ---
#     if initial_schedule:
#         events = [
#             {"type": "node_failure", "node_id": "N2", "time": 1}
#         ]
        
#         # --- 4. Run Phase 3 to handle the event ---
#         updated_schedule, result = run_phase3_dynamic_reallocation(
#             initial_schedule,
#             initial_data,
#             events
#         )

#         if updated_schedule:
#             print("\n--- FINAL UPDATED SCHEDULE AFTER EVENT ---")
#             # Note: The cost might change, but for simplicity, we'll show the original.
#             # A more advanced model would recalculate the cost.
#             final_output = {
#                 "updated_schedule": updated_schedule,
#                 "original_cost": total_cost,
#                 "failed_tasks": result["failed_tasks"]
#             }
#             print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    # --- 1. Define the Initial State of the System ---
    initial_data = {
        "tasks": {
            "T1": {"cpu": 2, "ram": 4, "duration": 2, "deadline": 4, "priority": 1},
            "T2": {"cpu": 3, "ram": 2, "duration": 3, "deadline": 5, "priority": 2},
            "T3": {"cpu": 2, "ram": 3, "duration": 2, "deadline": 3, "priority": 3}, # Most urgent deadline
        },
        "nodes": {
            "N1": {"cpu_capacity": 7, "ram_capacity": 10},
        },
        "exec_costs": {
            "T1": {"N1": 2},
            "T2": {"N1": 5},
            "T3": {"N1": 3},
        },
        "time_slots": [0, 1, 2, 3, 4, 5],
        "node_capacity_per_time": {
           "N1": {"0": 5, "1": 5, "2": 5, "3": 5, "4": 5, "5": 5},
        }
    }

    # --- 2. Run Phase 1 to get the global assignments ---
    assignments, total_cost = run_phase1_allocation(
        initial_data["tasks"], 
        initial_data["nodes"], 
        initial_data["exec_costs"], 
        initial_data["node_capacity_per_time"]
    )
    
    if assignments:
        print("\nPhase 1 Assignments:", json.dumps(assignments, indent=2))
        
        # --- 3. Group tasks by their assigned node ---
        tasks_per_node = {node_id: {} for node_id in initial_data["nodes"]}
        for task_id, node_id in assignments.items():
            tasks_per_node[node_id][task_id] = initial_data["tasks"][task_id]

        # --- 4. Run the Phase 4 local scheduler for each node ---
        final_system_schedule = {}
        for node_id, assigned_tasks in tasks_per_node.items():
            if not assigned_tasks:
                continue
            
            node_schedule = run_phase4_local_scheduler(
            assigned_tasks,
            node_id,
            initial_data["nodes"][node_id], # <-- This was the missing argument
            initial_data["node_capacity_per_time"],
            initial_data["time_slots"]
            )
            final_system_schedule[node_id] = node_schedule

        print("\n--- FINAL SYSTEM SCHEDULE (from Phase 4 Local Schedulers) ---")
        print(json.dumps(final_system_schedule, indent=2))