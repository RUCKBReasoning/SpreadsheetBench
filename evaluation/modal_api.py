import os
import json
import tempfile
import modal
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GOOGLE_ACCESS_KEY_ID") or not os.getenv("GOOGLE_ACCESS_KEY_SECRET"):
    raise ValueError("GOOGLE_ACCESS_KEY_ID and GOOGLE_ACCESS_KEY_SECRET must be set")

# Create Modal app
app = modal.App("spreadsheet-eval-api")

# Create Modal image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "tqdm==4.66.3", "pandas==2.2.0", "openpyxl==3.1.3", "numpy>=1.23.2", "fastapi", "boto3", "python-dotenv"
    )
    .add_local_dir(local_path="data", remote_path="/root/data", copy=True)
    .add_local_file(
        local_path="evaluation/evaluation.py",
        remote_path="/root/evaluation.py",
        copy=True,
    )
    .run_commands("cd /root/data && tar -xzf all_data_912.tar.gz")
    .env({"GOOGLE_ACCESS_KEY_ID": os.getenv("GOOGLE_ACCESS_KEY_ID"), "GOOGLE_ACCESS_KEY_SECRET": os.getenv("GOOGLE_ACCESS_KEY_SECRET")})
)


def _evaluate_spreadsheet_bytes(spreadsheet_id: str, outputs_bytes: dict) -> dict:
    """
    Helper function that evaluates spreadsheet bytes against ground truth.
    
    Args:
        spreadsheet_id: The spreadsheet ID
        outputs_bytes: Dict mapping test case idx (as int) to file bytes
                      Example: {0: b'...xlsx bytes...', 1: b'...', 2: b'...'}
    
    Returns:
        Dict with evaluation results
    """
    import sys
    sys.path.insert(0, "/root")
    from evaluation import compare_workbooks
    
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
            if test_case_idx not in outputs_bytes:
                test_case_results[test_case_idx] = None
                messages[test_case_idx] = f"Test case {test_case_idx + 1}: Not provided"
                continue
            
            # Create temporary file for the uploaded spreadsheet
            temp_file = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            temp_file.write(outputs_bytes[test_case_idx])
            temp_file.close()
            temp_files.append(temp_file.name)
            
            # Get ground truth file path for this test case
            gt_path = f"{dataset_path}/spreadsheet/{spreadsheet_id}/{test_case_idx + 1}_{spreadsheet_id}_answer.xlsx"
            
            if not os.path.exists(gt_path):
                test_case_results[test_case_idx] = False
                messages[test_case_idx] = f"Test case {test_case_idx + 1}: Ground truth file not found"
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
                messages[test_case_idx] = f"Test case {test_case_idx + 1}: Error - {str(e)}"
    
    finally:
        # Clean up all temporary files
        for temp_file_path in temp_files:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    # Calculate scores
    scoring_results = [r if r is not None else False for r in test_case_results]
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


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
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

        # Decode base64 to bytes
        outputs_bytes = {}
        for test_case_key, base64_data in outputs.items():
            try:
                test_case_idx = int(test_case_key)
                file_bytes = base64.b64decode(base64_data)
                outputs_bytes[test_case_idx] = file_bytes
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "message": f"Error decoding test case {test_case_key}: {str(e)}",
                    "id": spreadsheet_id,
                }

        # Call helper function
        return _evaluate_spreadsheet_bytes(spreadsheet_id, outputs_bytes)

    except Exception as e:
        return {
            "success": False,
            "result": None,
            "message": f"Error during evaluation: {str(e)}",
            "id": request_data.get("id", "unknown"),
        }


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def evaluate_gcp(request_data: dict):
    """
    API endpoint to evaluate a spreadsheet file from GCS against ground truth.
    
    Expected request format:
    {
        "id": "spreadsheet_id",
        "object_key": "path/to/file.xlsx"
    }
    
    Returns:
    Same format as evaluate_spreadsheet endpoint
    """
    import boto3
    from botocore.config import Config
    
    BUCKET = "shortcut_bg_task"
    
    try:
        spreadsheet_id = request_data.get("id")
        object_key = request_data.get("object_key")
        
        if not spreadsheet_id:
            return {
                "success": False,
                "result": None,
                "message": "Missing required parameter: 'id'",
                "id": None,
            }
        
        if not object_key:
            return {
                "success": False,
                "result": None,
                "message": "Missing required parameter: 'object_key'",
                "id": spreadsheet_id,
            }
        
        # Download file from GCS using S3-compatible API
        s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("GCS_XML_ENDPOINT", "https://storage.googleapis.com"),
            aws_access_key_id=os.environ["GOOGLE_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["GOOGLE_ACCESS_KEY_SECRET"],
            region_name="auto",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        
        # Download to temp file then read bytes
        temp_file = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        temp_file.close()
        
        try:
            s3.download_file(BUCKET, object_key, temp_file.name)
            with open(temp_file.name, "rb") as f:
                file_bytes = f.read()
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
        # Call helper function with only test case 0
        return _evaluate_spreadsheet_bytes(spreadsheet_id, {0: file_bytes})
    
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
