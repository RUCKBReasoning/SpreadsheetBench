"""
Script to find validation issues in evaluation.py using Modal API.

This script checks all 912 data points to identify cases where:
- Input files incorrectly pass validation as answer files
- This indicates bugs in evaluation.py's compare_workbooks function

The script does NOT fix evaluation.py, it only reports problematic cases.
Uses the Modal API endpoint to perform comparisons.

Usage:
    python find_validation_issues.py --url <modal_api_url>

Example:
    python find_validation_issues.py --url https://your-app.modal.run

Output:
    - Creates validation_issues.json with all problematic cases
    - Shows summary statistics grouped by instruction type
"""

import os
import json
import sys
import argparse
import base64
import requests
from tqdm import tqdm


def check_all_data_points(dataset_path, api_url):
    """
    Check all data points for validation issues.

    Returns:
        List of dicts containing problematic cases
    """
    # Load dataset
    with open(f"{dataset_path}/dataset.json", "r") as fp:
        dataset = json.load(fp)

    print(f"Checking {len(dataset)} spreadsheets...")
    print("=" * 80)

    problematic_cases = []
    api_calls_made = 0
    skipped_count = 0

    for data in tqdm(dataset, desc="Checking spreadsheets"):
        spreadsheet_id = data["id"]

        # Prepare outputs dict with available input files
        outputs = {}

        for test_case_idx in range(3):
            test_case_num = test_case_idx + 1
            input_path = f"{dataset_path}/spreadsheet/{spreadsheet_id}/{test_case_num}_{spreadsheet_id}_input.xlsx"

            if not os.path.exists(input_path):
                continue

            # Read and encode input file
            try:
                with open(input_path, "rb") as f:
                    file_bytes = f.read()
                    outputs[str(test_case_idx)] = base64.b64encode(file_bytes).decode(
                        "utf-8"
                    )
            except Exception:
                continue

        # Skip if no input files exist at all
        if not outputs:
            skipped_count += 1
            continue

        # Call Modal API with input files as if they were outputs
        try:
            response = requests.post(
                api_url, json={"id": spreadsheet_id, "outputs": outputs}, timeout=120
            )
            api_calls_made += 1

            if response.status_code != 200:
                continue

            result = response.json()

            if not result.get("success"):
                continue

            # Check each test case
            test_case_results = result.get("test_case_results", [])
            messages = result.get("messages", [])

            for test_case_idx in range(3):
                # If input passes as answer for this test case, that's a problem!
                if test_case_results[test_case_idx] is True:
                    problematic_cases.append(
                        {
                            "id": spreadsheet_id,
                            "test_case": test_case_idx + 1,
                            "instruction_type": data["instruction_type"],
                            "answer_position": data["answer_position"],
                            "comparison_message": messages[test_case_idx]
                            if test_case_idx < len(messages)
                            else "",
                            "issue": "Input file incorrectly passes as answer file",
                        }
                    )

        except Exception:
            # Skip cases with errors
            pass

    return problematic_cases, api_calls_made, skipped_count


def main():
    parser = argparse.ArgumentParser(
        description="Find validation issues in evaluation.py using Modal API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Modal API endpoint URL (required)",
    )

    parser.add_argument(
        "--dataset",
        default="data_copy/all_data_912",
        help="Path to dataset directory (default: data_copy/all_data_912)",
    )

    args = parser.parse_args()

    # Path to dataset
    dataset_path = os.path.abspath(args.dataset)

    if not os.path.exists(dataset_path):
        print(f"Error: Dataset path not found: {dataset_path}")
        print("Please extract all_data_912.tar.gz first:")
        print("  tar -xzf data/all_data_912.tar.gz -C data/")
        sys.exit(1)

    print(f"Using Modal API: {args.url}")
    print(f"Dataset path: {dataset_path}")
    print()

    # Check all data points
    problematic_cases, api_calls_made, skipped_count = check_all_data_points(
        dataset_path, args.url
    )

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Total spreadsheets checked: 912")
    print(f"API calls made: {api_calls_made}")
    print(f"Skipped (no input files): {skipped_count}")
    print(f"Total problematic cases found: {len(problematic_cases)}")

    if problematic_cases:
        print("\nBreakdown by instruction type:")
        type_counts = {}
        for case in problematic_cases:
            itype = case["instruction_type"]
            type_counts[itype] = type_counts.get(itype, 0) + 1

        for itype, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {itype}: {count}")

        print("\nFirst 10 problematic cases:")
        for i, case in enumerate(problematic_cases[:10]):
            print(
                f"  {i + 1}. ID: {case['id']}, Test case: {case['test_case']}, Type: {case['instruction_type']}"
            )

    # Write to JSON
    output_file = "validation_issues.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "summary": {
                    "total_spreadsheets": 912,
                    "api_calls_made": api_calls_made,
                    "skipped_no_input_files": skipped_count,
                    "total_problematic_cases": len(problematic_cases),
                    "affected_spreadsheets": len(
                        set(c["id"] for c in problematic_cases)
                    ),
                    "description": "Cases where input files incorrectly pass validation as answer files",
                },
                "problematic_cases": problematic_cases,
            },
            f,
            indent=2,
        )

    print(f"\n✓ Results written to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
