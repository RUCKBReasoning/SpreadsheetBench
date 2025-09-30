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
    API endpoint to evaluate a spreadsheet file against ground truth.

    Expected request format:
    {
        "id": "spreadsheet_id",
        "file_blob": "base64_encoded_xlsx_file"
    }

    Returns:
    {
        "success": bool,
        "result": bool or None,
        "message": str,
        "id": str
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
        file_blob = request_data.get("file_blob")

        if not spreadsheet_id or not file_blob:
            return {
                "success": False,
                "result": None,
                "message": "Missing required parameters: 'id' and 'file_blob' are required",
                "id": spreadsheet_id,
            }

        # Load dataset to get ground truth info
        dataset_path = "/root/data/all_data_912"
        with open(f"{dataset_path}/dataset.json", "r") as fp:
            dataset = json.load(fp)

        # Find the data entry for this ID
        data_entry = None
        for data in dataset:
            if data["id"] == spreadsheet_id:
                data_entry = data
                break

        if data_entry is None:
            return {
                "success": False,
                "result": None,
                "message": f"Spreadsheet ID '{spreadsheet_id}' not found in dataset",
                "id": spreadsheet_id,
            }

        # Decode base64 file blob
        file_bytes = base64.b64decode(file_blob)

        # Create temporary file for the uploaded spreadsheet
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        # Evaluate against all 3 test cases
        test_case_results = []
        messages = []

        for test_case_idx in range(3):
            gt_path = f"{dataset_path}/spreadsheet/{spreadsheet_id}/{test_case_idx + 1}_{spreadsheet_id}_answer.xlsx"

            if not os.path.exists(gt_path):
                test_case_results.append(False)
                messages.append(
                    f"Test case {test_case_idx + 1}: Ground truth file not found"
                )
                continue

            try:
                # Compare workbooks
                result, message = compare_workbooks(
                    gt_path,
                    temp_file_path,
                    data_entry["instruction_type"],
                    data_entry["answer_position"],
                )
                test_case_results.append(bool(result))
                messages.append(f"Test case {test_case_idx + 1}: {message}")
            except Exception as e:
                test_case_results.append(False)
                messages.append(f"Test case {test_case_idx + 1}: Error - {str(e)}")

        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

        # Calculate scores
        soft_restriction = test_case_results.count(True) / len(test_case_results)
        hard_restriction = 0 if False in test_case_results else 1

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
