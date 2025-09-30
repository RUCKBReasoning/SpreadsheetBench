"""
Test script for the Modal Spreadsheet Evaluation API endpoint.
"""

import requests
import base64
import sys

# The deployed Modal endpoint
API_URL = "https://fairies--spreadsheet-eval-api-evaluate-spreadsheet.modal.run"


def test_evaluation_api(spreadsheet_id: str, file_path: str):
    """
    Test the Modal evaluation API with a spreadsheet file.

    Args:
        spreadsheet_id: The ID of the spreadsheet from the dataset
        file_path: Path to the .xlsx file to evaluate

    Returns:
        Dictionary with evaluation results
    """

    print(f"Testing spreadsheet ID: {spreadsheet_id}")
    print(f"File: {file_path}")
    print("-" * 80)

    # Read and encode the file
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        file_blob = base64.b64encode(file_bytes).decode("utf-8")

    print(f"File encoded, size: {len(file_blob)} bytes (base64)")

    # Prepare request data
    request_data = {
        "id": spreadsheet_id,
        "file_blob": file_blob,
    }

    print("Sending request to API...")

    try:
        # Call deployed Modal API endpoint
        response = requests.post(API_URL, json=request_data, timeout=60)

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
            print(f"✓ Soft Restriction (% passed): {result['soft_restriction']:.2%}")
            print(f"✓ Hard Restriction (all passed): {result['hard_restriction']}")
            print("\nDetailed Messages:")
            for message in result["messages"]:
                print(f"  • {message}")
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


def main():
    """Test with sample data from all_data_912"""

    print("\n" + "=" * 80)
    print("Modal Spreadsheet Evaluation API - Test Suite")
    print("=" * 80)
    print(f"Endpoint: {API_URL}")
    print("=" * 80 + "\n")

    # Test Case 1: Use an answer file (should pass perfectly)
    print("=" * 80)
    print("TEST 1: Testing with ANSWER file (should get 100% pass)")
    print("=" * 80 + "\n")

    test_evaluation_api(
        spreadsheet_id="13-1",
        file_path="data_copy/all_data_912/spreadsheet/13-1/1_13-1_answer.xlsx",
    )

    print("\n\n" + "=" * 80)
    print("TEST 2: Testing with INPUT file (should likely fail)")
    print("=" * 80 + "\n")

    # Test Case 2: Use an input file (should fail since it's not the answer)
    test_evaluation_api(
        spreadsheet_id="13-1",
        file_path="data_copy/all_data_912/spreadsheet/13-1/1_13-1_input.xlsx",
    )

    print("\n\n" + "=" * 80)
    print("TEST 3: Testing with different spreadsheet ID")
    print("=" * 80 + "\n")

    # Test Case 3: Test with a different spreadsheet
    test_evaluation_api(
        spreadsheet_id="17-35",
        file_path="data_copy/all_data_912/spreadsheet/17-35/1_17-35_answer.xlsx",
    )

    print("\n\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Allow command line usage
        spreadsheet_id = sys.argv[1]
        file_path = sys.argv[2]
        test_evaluation_api(spreadsheet_id, file_path)
    else:
        main()
