import os
import json
import tempfile
import modal

# Create Modal app
app = modal.App("spreadsheet-eval-api")

# Create Modal image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "tqdm==4.66.3", "pandas==2.2.0", "openpyxl==3.1.3", "numpy>=1.23.2", "fastapi"
    )
    .add_local_dir(local_path="data", remote_path="/root/data", copy=True)
    .add_local_file(
        local_path="evaluation/evaluation.py",
        remote_path="/root/evaluation.py",
        copy=True,
    )
    .run_commands("cd /root/data && tar -xzf all_data_912.tar.gz")
)


@app.function(image=image)
@modal.web_endpoint(method="POST")
def evaluate_spreadsheet(request_data: dict):
    """
    API endpoint to evaluate spreadsheet files against ground truth.

    Expected request format:
    {
        "id": "spreadsheet_id",
        "outputs": {
            "0": "base64_encoded_xlsx_file_for_test_case_1",
            "1": "base64_encoded_xlsx_file_for_test_case_2",
            "2": "base64_encoded_xlsx_file_for_test_case_3"
        }
    }

    Note: You can omit test cases if outputs are not available.

    Returns:
    {
        "success": bool,
        "result": bool,  # True if hard_restriction == 1
        "id": str,
        "instruction_type": str,
        "test_case_results": [bool, bool, bool],  # None for missing outputs
        "soft_restriction": float,  # percentage of available tests that passed
        "hard_restriction": int,  # 1 if all available tests passed, 0 otherwise
        "messages": [str, str, str]
    }
    """
    import base64
    import sys

    # Add evaluation module to path and import
    sys.path.insert(0, "/root")
    from evaluation import compare_workbooks

    # Parse request
    try:
        spreadsheet_id = request_data.get("id")
        outputs = request_data.get("outputs")

        if not spreadsheet_id:
            return {
                "success": False,
                "result": None,
                "message": "Missing required parameter: 'id'",
                "id": None,
            }

        if not outputs or not isinstance(outputs, dict):
            return {
                "success": False,
                "result": None,
                "message": "Missing or invalid 'outputs' parameter. Expected a dict with keys '0', '1', '2'",
                "id": spreadsheet_id,
            }

        # Load dataset to get ground truth info
        dataset_path = "/root/data/all_data_912"
        with open(f"{dataset_path}/dataset.json", "r") as fp:
            dataset = json.load(fp)

        # Find the data entry for this ID
        data_entry = None
        for data in dataset:
            if str(data["id"]) == spreadsheet_id:
                data_entry = data
                break

        if data_entry is None:
            return {
                "success": False,
                "result": None,
                "message": f"Spreadsheet ID '{spreadsheet_id}' not found in dataset",
                "id": spreadsheet_id,
            }

        # Evaluate each provided test case
        test_case_results = [None, None, None]
        messages = ["", "", ""]
        temp_files = []

        try:
            for test_case_idx in range(3):
                test_case_key = str(test_case_idx)

                if test_case_key not in outputs:
                    test_case_results[test_case_idx] = None
                    messages[test_case_idx] = (
                        f"Test case {test_case_idx + 1}: Not provided"
                    )
                    continue

                # Decode base64 file blob
                try:
                    file_bytes = base64.b64decode(outputs[test_case_key])
                except Exception as e:
                    test_case_results[test_case_idx] = False
                    messages[test_case_idx] = (
                        f"Test case {test_case_idx + 1}: Error decoding base64 - {str(e)}"
                    )
                    continue

                # Create temporary file for the uploaded spreadsheet
                temp_file = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                temp_file.write(file_bytes)
                temp_file.close()
                temp_files.append(temp_file.name)

                # Get ground truth file path for this test case
                gt_path = f"{dataset_path}/spreadsheet/{spreadsheet_id}/{test_case_idx + 1}_{spreadsheet_id}_answer.xlsx"

                if not os.path.exists(gt_path):
                    test_case_results[test_case_idx] = False
                    messages[test_case_idx] = (
                        f"Test case {test_case_idx + 1}: Ground truth file not found"
                    )
                    continue

                # Compare workbooks
                try:
                    result, message = compare_workbooks(
                        gt_path,
                        temp_file.name,
                        data_entry["instruction_type"],
                        data_entry["answer_position"],
                    )
                    test_case_results[test_case_idx] = bool(result)
                    messages[test_case_idx] = (
                        f"Test case {test_case_idx + 1}: {message}"
                        if message
                        else f"Test case {test_case_idx + 1}: Match"
                    )
                except Exception as e:
                    test_case_results[test_case_idx] = False
                    messages[test_case_idx] = (
                        f"Test case {test_case_idx + 1}: Error - {str(e)}"
                    )

        finally:
            # Clean up all temporary files
            for temp_file_path in temp_files:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        # Calculate scores (matching evaluation.py logic)
        # In evaluation.py, missing files count as failures (0)
        # So we convert None to False for scoring
        scoring_results = [r if r is not None else False for r in test_case_results]

        # soft_restriction: always divide by 3 (total test cases)
        # hard_restriction: 1 only if all 3 test cases pass
        soft_restriction = scoring_results.count(True) / 3
        hard_restriction = 0 if False in scoring_results else 1

        return {
            "success": True,
            "result": hard_restriction == 1,
            "id": spreadsheet_id,
            "instruction_type": data_entry["instruction_type"],
            "test_case_results": test_case_results,
            "soft_restriction": soft_restriction,
            "hard_restriction": hard_restriction,
            "messages": messages,
        }

    except Exception as e:
        return {
            "success": False,
            "result": None,
            "message": f"Error during evaluation: {str(e)}",
            "id": request_data.get("id", "unknown"),
        }


@app.local_entrypoint()
def main():
    """Test the API locally"""
    print("Modal app deployed successfully!")
    print("To deploy: modal deploy evaluation/modal_api.py")
    print("To test: modal run evaluation/modal_api.py")
