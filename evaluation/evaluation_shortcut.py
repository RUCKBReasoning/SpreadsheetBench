import os
import json
import argparse
from tqdm import tqdm
from ooxml import ensure_ooxml_compliance
from evaluation import compare_workbooks


def parse_option():
    parser = argparse.ArgumentParser("command line arguments for evaluation.")

    parser.add_argument(
        "--dataset", type=str, default="all_data_912", help="dataset name"
    )
    parser.add_argument(
        "--results_folder",
        type=str,
        required=True,
        help="Path to results folder with timestamped output files",
    )
    parser.add_argument(
        "--run",
        type=int,
        default=1,
        help="Which test set/run to evaluate (1, 2, or 3). Default is 1.",
    )

    opt = parser.parse_args()

    return opt


def find_result_file(results_folder, data_id, run_number):
    """Check if result file exists for this task ID and run number.

    Simply checks if any file contains the pattern: output_{data_id}_*_run_{run_number}.xlsx
    """
    # Check if file exists with this pattern
    for filename in os.listdir(results_folder):
        if filename.startswith(f"output_{data_id}_") and filename.endswith(
            f"_run_{run_number}.xlsx"
        ):
            return os.path.join(results_folder, filename)
    return None


def evaluation(opt):
    dataset_path = os.path.abspath(f"../data/{opt.dataset}")
    with open(f"{dataset_path}/dataset.json", "r") as fp:
        dataset = json.load(fp)

    print(f"Evaluating {len(dataset)} tasks from {opt.dataset}")
    print(f"Using results folder: {opt.results_folder}")
    print(f"Evaluating run {opt.run}")

    eval_results = []

    for data in tqdm(dataset):
        test_case_idx = opt.run
        gt_path = f"{dataset_path}/spreadsheet/{data['id']}/{test_case_idx}_{data['id']}_answer.xlsx"

        # Check if output file exists
        proc_path = find_result_file(opt.results_folder, data["id"], opt.run)

        if proc_path is None:
            # Skip tasks without output files
            continue

        if not os.path.exists(proc_path):
            continue

        # Ensure OOXML compliance for the output file
        proc_path = ensure_ooxml_compliance(proc_path)

        try:
            result, msg = compare_workbooks(
                gt_path,
                proc_path,
                data["instruction_type"],
                data["answer_position"],
            )
        except Exception as e:
            result = False
            msg = str(e)

        eval_results.append(
            {
                "id": data["id"],
                "instruction_type": data["instruction_type"],
                "result": int(result),
                "success": result,
                "error_msg": msg if not result else "",
            }
        )

    # Print summary
    evaluated_count = len(eval_results)
    correct = sum(1 for r in eval_results if r["success"])
    accuracy = correct / evaluated_count if evaluated_count > 0 else 0

    print(f"\nEvaluated {evaluated_count} tasks with output files")
    print(f"Accuracy: {accuracy:.2%} ({correct}/{evaluated_count})")

    # Save results
    folder_name = os.path.basename(opt.results_folder)
    output_path = f"../outputs/eval_{folder_name}_run{opt.run}.json"

    with open(output_path, "w") as fp:
        json.dump(eval_results, fp, indent=4)

    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    opt = parse_option()
    print(opt)

    evaluation(opt)
