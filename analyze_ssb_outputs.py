#!/usr/bin/env python3
"""
Analyze SSB outputs across multiple runs and generate CSV with scores per task.
"""

import json
import os
import csv
from pathlib import Path
from typing import Dict, List, Optional


def load_json_results(json_path: str) -> Dict[str, float]:
    """Load JSON results and return dict mapping task_id to score."""
    with open(json_path, "r") as f:
        data = json.load(f)

    results = {}
    for entry in data:
        # Normalize task_id to string (JSON has mixed int/str types)
        task_id = str(entry["id"])
        # Use result as score (1 for success, 0 for failure)
        score = entry["result"]
        results[task_id] = score

    return results


def get_all_task_ids(spreadsheet_dir: str) -> List[str]:
    """Get all task IDs from the spreadsheet directory."""
    task_ids = []
    for item in sorted(os.listdir(spreadsheet_dir)):
        path = os.path.join(spreadsheet_dir, item)
        if os.path.isdir(path):
            task_ids.append(item)
    return task_ids


def main():
    # Paths
    ssb_outputs_dir = "ssb_outputs_2"
    spreadsheet_dir = "data/all_data_912/spreadsheet"
    output_csv = "ssb_scores_per_task.csv"

    # Get all JSON files
    json_files = sorted(
        [
            os.path.join(ssb_outputs_dir, f)
            for f in os.listdir(ssb_outputs_dir)
            if f.endswith(".json")
        ]
    )

    print(f"Found {len(json_files)} JSON files:")
    for jf in json_files:
        print(f"  - {jf}")

    # Load results from each run
    run_results = []
    for json_file in json_files:
        results = load_json_results(json_file)
        run_results.append(results)
        print(f"Loaded {len(results)} results from {os.path.basename(json_file)}")

    # Get all task IDs
    all_task_ids = get_all_task_ids(spreadsheet_dir)
    print(f"\nTotal tasks in dataset: {len(all_task_ids)}")

    # Create CSV with scores per task
    print(f"\nWriting CSV to {output_csv}...")
    with open(output_csv, "w", newline="") as csvfile:
        fieldnames = ["task_id"] + [f"run_{i + 1}" for i in range(len(json_files))]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for task_id in all_task_ids:
            row = {"task_id": task_id}
            for i, run_result in enumerate(run_results):
                # Use None/empty for tasks that didn't complete
                row[f"run_{i + 1}"] = run_result.get(task_id, "")
            writer.writerow(row)

    print(f"CSV written successfully!")

    # Analysis 1: % failures per run (tasks that didn't run/missing from JSON)
    print("\n" + "=" * 60)
    print("ANALYSIS 1: Task Failure Rate Per Run (Missing from JSON)")
    print("=" * 60)
    for i, run_result in enumerate(run_results):
        total_tasks = len(all_task_ids)
        completed_tasks = len(run_result)
        failed_tasks = total_tasks - completed_tasks
        failure_rate = (failed_tasks / total_tasks) * 100
        print(
            f"Run {i + 1}: {failed_tasks}/{total_tasks} tasks didn't run ({failure_rate:.2f}%)"
        )

    # Average success rate per run (for tasks that ran)
    print("\n" + "=" * 60)
    print("ANALYSIS 1.5: Average Success Rate Per Run (For Completed Tasks)")
    print("=" * 60)
    for i, run_result in enumerate(run_results):
        if run_result:
            avg_success = sum(run_result.values()) / len(run_result)
            print(f"Run {i + 1}: {avg_success:.4f} ({len(run_result)} tasks completed)")
        else:
            print(f"Run {i + 1}: No tasks completed")

    # Analysis 2: Tasks that failed (missing) across all 4 runs
    print("\n" + "=" * 60)
    print("ANALYSIS 2: Tasks That Failed (Missing) Across All Runs")
    print("=" * 60)
    failed_all_runs = []
    for task_id in all_task_ids:
        # Check if task is missing from all runs
        missing_in_all = all(task_id not in run_result for run_result in run_results)
        if missing_in_all:
            failed_all_runs.append(task_id)

    print(
        f"Total tasks that failed in all {len(json_files)} runs: {len(failed_all_runs)}"
    )
    if failed_all_runs:
        print("\nTasks:")
        for task_id in failed_all_runs[:20]:  # Show first 20
            print(f"  - {task_id}")
        if len(failed_all_runs) > 20:
            print(f"  ... and {len(failed_all_runs) - 20} more")

    # Analysis 3: Average of average task scores (excluding tasks that didn't run)
    print("\n" + "=" * 60)
    print("ANALYSIS 3: Average Task Scores (Excluding Missing Tasks)")
    print("=" * 60)

    task_averages = []
    task_details = []
    for task_id in all_task_ids:
        scores = []
        for run_result in run_results:
            if task_id in run_result:
                scores.append(run_result[task_id])

        if scores:  # Only compute average if task ran at least once
            avg_score = sum(scores) / len(scores)
            task_averages.append(avg_score)
            task_details.append(
                {
                    "task_id": task_id,
                    "scores": scores,
                    "avg": avg_score,
                    "num_runs": len(scores),
                }
            )

    if task_averages:
        overall_average = sum(task_averages) / len(task_averages)
        print(f"Number of tasks that ran at least once: {len(task_averages)}")
        print(f"Average of average task scores: {overall_average:.4f}")

        # Show some examples to verify
        print(f"\nSample of task averages (first 10):")
        for detail in task_details[:10]:
            print(
                f"  {detail['task_id']}: scores={detail['scores']}, avg={detail['avg']:.2f}, runs={detail['num_runs']}"
            )

        # Count how many tasks have perfect scores
        perfect_tasks = sum(1 for avg in task_averages if avg == 1.0)
        zero_tasks = sum(1 for avg in task_averages if avg == 0.0)
        print(f"\nTasks with perfect avg (1.0): {perfect_tasks}")
        print(f"Tasks with zero avg (0.0): {zero_tasks}")
        print(
            f"Tasks with mixed results: {len(task_averages) - perfect_tasks - zero_tasks}"
        )
    else:
        print("No tasks ran in any run!")

    # Additional stats
    print("\n" + "=" * 60)
    print("ADDITIONAL STATISTICS")
    print("=" * 60)
    print(f"Total unique tasks in dataset: {len(all_task_ids)}")
    print(f"Tasks that ran at least once: {len(task_averages)}")
    print(f"Tasks that never ran: {len(all_task_ids) - len(task_averages)}")


if __name__ == "__main__":
    main()
