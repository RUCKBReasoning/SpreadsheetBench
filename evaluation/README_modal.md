# Modal API for Spreadsheet Evaluation

This Modal app provides an API endpoint for evaluating spreadsheet files against ground truth data from the SpreadsheetBench dataset.

## Deployment

Deploy the Modal app **from the project root directory**:

```bash
modal deploy evaluation/modal_api.py
```

## Verification

After deployment, verify the endpoint is working correctly:

```bash
# Extract test data
tar -xzf data/all_data_912.tar.gz -C data_copy all_data_912/spreadsheet/13-1/

# Run the test script
python evaluation/test_endpoint.py 13-1 data_copy/all_data_912/spreadsheet/13-1/1_13-1_answer.xlsx
```

**Expected output for a passing test:**
```
================================================================================
EVALUATION RESULTS
================================================================================
✓ Success: True
✓ Overall Result: PASS
✓ ID: 13-1
✓ Instruction Type: Sheet-Level Manipulation
✓ Test Case Results: [True, True, True]
✓ Soft Restriction (% passed): 100.00%
✓ Hard Restriction (all passed): 1
```

See `evaluation/test_endpoint.py` for the complete test implementation.

## Usage

### API Endpoint

The API accepts POST requests with the following JSON format:

```json
{
  "id": "spreadsheet_id",
  "file_blob": "base64_encoded_xlsx_file"
}
```

**Parameters:**
- `id` (required): The spreadsheet ID from the dataset
- `file_blob` (required): Base64-encoded .xlsx file content

**Response:**
```json
{
  "success": true,
  "result": true,
  "id": "spreadsheet_id",
  "instruction_type": "Data Transformation",
  "test_case_results": [true, true, true],
  "soft_restriction": 1.0,
  "hard_restriction": 1,
  "messages": [
    "Test case 1: Cell values in the specified range are identical.",
    "Test case 2: Cell values in the specified range are identical.",
    "Test case 3: Cell values in the specified range are identical."
  ]
}
```

**Response Fields:**
- `success`: Whether the API call was successful
- `result`: Overall pass/fail (true if all test cases pass)
- `id`: The spreadsheet ID
- `instruction_type`: The type of instruction from the dataset
- `test_case_results`: Array of boolean results for each of the 3 test cases
- `soft_restriction`: Score from 0.0 to 1.0 (percentage of passing test cases)
- `hard_restriction`: 0 or 1 (1 only if all test cases pass)
- `messages`: Detailed messages for each test case
