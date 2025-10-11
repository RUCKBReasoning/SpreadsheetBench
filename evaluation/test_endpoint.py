"""
Test script for the Modal Spreadsheet Evaluation API endpoint.
"""

import requests
import base64
import sys
import os
import argparse


def test_evaluation_api(spreadsheet_id: str, outputs_dict: dict, api_url: str):
    """
    Test the Modal evaluation API with spreadsheet files.

    Args:
        spreadsheet_id: The ID of the spreadsheet from the dataset
        outputs_dict: Dictionary mapping test case idx (as int) to file paths
                     Example: {0: "path/to/file1.xlsx", 2: "path/to/file3.xlsx"}
        api_url: Optional API URL (defaults to API_URL global/env var)

    Returns:
        Dictionary with evaluation results
    """

    # Use provided URL or fall back to default
    url = api_url

    print(f"Testing spreadsheet ID: {spreadsheet_id}")
    print(f"API URL: {url}")
    print(f"Test cases provided: {list(outputs_dict.keys())}")
    print("-" * 80)

    # Prepare outputs dict with base64-encoded files
    outputs = {}
    for test_case_idx, file_path in outputs_dict.items():
        print(f"Loading test case {test_case_idx + 1}: {file_path}")
        if not os.path.exists(file_path):
            print("  ⚠ File not found, skipping")
            continue

        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_blob = base64.b64encode(file_bytes).decode("utf-8")
            outputs[str(test_case_idx)] = file_blob
            print(f"  ✓ Encoded, size: {len(file_blob)} bytes (base64)")

    if not outputs:
        print("No valid files to evaluate!")
        return None

    # Prepare request data
    request_data = {
        "id": spreadsheet_id,
        "outputs": outputs,
    }

    print(f"\nSending request to API with {len(outputs)} output(s)...")

    try:
        # Call deployed Modal API endpoint
        response = requests.post(url, json=request_data, timeout=60)

        print(f"Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"Error: {response.text}")
            return None

        result = response.json()

        print("\n" + "=" * 80)
        print("EVALUATION RESULTS")
        print("=" * 80)

        if result["success"]:
            print(f"✓ Success: {result['success']}")
            print(f"✓ Overall Result: {'PASS' if result['result'] else 'FAIL'}")
            print(f"✓ ID: {result['id']}")
            print(f"✓ Instruction Type: {result['instruction_type']}")
            print(f"✓ Test Case Results: {result['test_case_results']}")
            print(f"✓ Soft Restriction: {result['soft_restriction']:.2%}")
            print(f"✓ Hard Restriction: {result['hard_restriction']}")
            print("\nDetailed Messages:")
            for msg in result["messages"]:
                if msg:
                    print(f"  • {msg}")
        else:
            print(f"✗ Error: {result.get('message', 'Unknown error')}")

        print("=" * 80)

        return result

    except requests.exceptions.Timeout:
        print("Error: Request timed out")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def main(api_url):
    """Test with sample data from all_data_912"""

    print("\n" + "=" * 80)
    print("Modal Spreadsheet Evaluation API - Test Suite")
    print("=" * 80)
    print(f"Endpoint: {api_url}")
    print("=" * 80 + "\n")

    # Test Case 1: All 3 answer files (should get 100% pass)
    print("=" * 80)
    print("TEST 1: All 3 answer files (should PASS 100%)")
    print("=" * 80 + "\n")

    test_evaluation_api(
        spreadsheet_id="17-35",
        outputs_dict={
            0: "data_copy/all_data_912/spreadsheet/17-35/1_17-35_answer.xlsx",
            1: "data_copy/all_data_912/spreadsheet/17-35/2_17-35_answer.xlsx",
            2: "data_copy/all_data_912/spreadsheet/17-35/3_17-35_answer.xlsx",
        },
        api_url=api_url,
    )

    print("\n\n" + "=" * 80)
    print("TEST 2: Only 2 answer files (should get soft_restriction=2/3=0.67)")
    print("=" * 80 + "\n")

    # Test Case 2: Only provide 2 out of 3 test cases
    # Missing test case counts as failure, so soft_restriction = 2/3
    test_evaluation_api(
        spreadsheet_id="17-35",
        outputs_dict={
            0: "data_copy/all_data_912/spreadsheet/17-35/1_17-35_answer.xlsx",
            2: "data_copy/all_data_912/spreadsheet/17-35/3_17-35_answer.xlsx",
        },
        api_url=api_url,
    )

    print("\n\n" + "=" * 80)
    print("TEST 3: Mix of answer and input files (soft_restriction=2/3=0.67)")
    print("=" * 80 + "\n")

    # Test Case 3: Mix of correct and incorrect files
    # 2 pass, 1 fail -> soft_restriction = 2/3
    test_evaluation_api(
        spreadsheet_id="17-35",
        outputs_dict={
            0: "data_copy/all_data_912/spreadsheet/17-35/1_17-35_answer.xlsx",  # Correct
            1: "data_copy/all_data_912/spreadsheet/17-35/2_17-35_input.xlsx",  # Wrong (input not answer)
            2: "data_copy/all_data_912/spreadsheet/17-35/3_17-35_answer.xlsx",  # Correct
        },
        api_url=api_url,
    )

    print("\n\n" + "=" * 80)
    print("TEST 4: Different spreadsheet with only 1 file")
    print("=" * 80 + "\n")

    # Test Case 4: Test with a different spreadsheet
    test_evaluation_api(
        spreadsheet_id="19-7",
        outputs_dict={
            0: "data_copy/all_data_912/spreadsheet/19-7/1_19-7_answer.xlsx",
        },
        api_url=api_url,
    )

    print("\n\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test the Modal Spreadsheet Evaluation API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full test suite
  python test_endpoint.py --url https://your-app.modal.run

  # Evaluate specific files
  python test_endpoint.py --url https://your-app.modal.run --id 13-1 --files file1.xlsx file2.xlsx file3.xlsx
        """,
    )

    parser.add_argument(
        "--url",
        required=True,
        help="API endpoint URL (required)",
    )

    parser.add_argument(
        "--id",
        dest="spreadsheet_id",
        help="Spreadsheet ID (required if --files is used)",
    )

    parser.add_argument(
        "--files",
        nargs="+",
        help="Output files to evaluate (up to 3 files for test cases 1, 2, 3)",
    )

    args = parser.parse_args()

    # If files are provided, require spreadsheet_id
    if args.files and not args.spreadsheet_id:
        parser.error("--id is required when --files is specified")

    # If spreadsheet_id is provided, require files
    if args.spreadsheet_id and not args.files:
        parser.error("--files is required when --id is specified")

    if args.spreadsheet_id and args.files:
        # Evaluate specific files
        outputs_dict = {}
        for i, file_path in enumerate(args.files):
            if os.path.exists(file_path):
                outputs_dict[i] = file_path
            else:
                print(f"Warning: File not found: {file_path}")

        if not outputs_dict:
            print("Error: No valid files found")
            sys.exit(1)

        test_evaluation_api(args.spreadsheet_id, outputs_dict, args.url)
    else:
        # Run full test suite
        main(args.url)
