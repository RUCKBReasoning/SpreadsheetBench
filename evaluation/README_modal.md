# Modal API for Spreadsheet Evaluation

This Modal app provides an API endpoint for evaluating spreadsheet files against ground truth data from the SpreadsheetBench dataset.

## Deployment

Deploy the Modal app **from the project root directory**:

```bash
modal deploy evaluation/modal_api.py
```

## Verification

After deployment, verify the endpoint is working correctly.

### Run Tests

The test script requires the `--url` parameter with your deployed API endpoint.

```bash
# Extract test data
tar -xzf data/all_data_912.tar.gz -C data_copy all_data_912/spreadsheet/17-35/

# Run full test suite
python evaluation/test_endpoint.py --url "modal url"

```

**Expected output for a passing test:**
```
================================================================================
EVALUATION RESULTS
================================================================================
✓ Success: True
✓ Overall Result: PASS
✓ ID: 17-35
✓ Instruction Type: Sheet-Level Manipulation
✓ Test Case Results: [True, True, True]
✓ Soft Restriction: 100.00%
✓ Hard Restriction: 1
```

See `evaluation/test_endpoint.py` for the complete test implementation.

## Usage

### Understanding Test Cases

Each spreadsheet task has **3 independent test cases**:
- Test case 1: `1_{id}_input.xlsx` → your model produces → `1_{id}_output.xlsx`
- Test case 2: `2_{id}_input.xlsx` → your model produces → `2_{id}_output.xlsx`
- Test case 3: `3_{id}_input.xlsx` → your model produces → `3_{id}_output.xlsx`

Each output file is evaluated against its corresponding answer file (`1_{id}_answer.xlsx`, `2_{id}_answer.xlsx`, `3_{id}_answer.xlsx`).

### API Endpoint

The API accepts POST requests with the following JSON format:

```json
{
  "id": "17-35",
  "outputs": {
    "0": "base64_encoded_xlsx_for_test_case_1",
    "1": "base64_encoded_xlsx_for_test_case_2",
    "2": "base64_encoded_xlsx_for_test_case_3"
  }
}
```

**Parameters:**
- `id` (required): The spreadsheet ID from the dataset
- `outputs` (required): Dictionary mapping test case index (as string "0", "1", "2") to base64-encoded .xlsx file content
  - You can omit test cases if outputs are not available (e.g., only provide `{"0": "...", "2": "..."}`)

**Response:**
```json
{
  "success": true,
  "result": true,
  "id": "17-35",
  "instruction_type": "Sheet-Level Manipulation",
  "test_case_results": [true, true, true],
  "soft_restriction": 1.0,
  "hard_restriction": 1,
  "messages": [
    "Test case 1: PASS - ",
    "Test case 2: PASS - ",
    "Test case 3: PASS - "
  ]
}
```

**Response Fields:**
- `success`: Whether the API call was successful
- `result`: True if `hard_restriction == 1` (all 3 test cases passed)
- `id`: The spreadsheet ID
- `instruction_type`: The type of instruction from the dataset
- `test_case_results`: Array of results for each test case (`true`/`false`/`null` for not provided)
- `soft_restriction`: Ratio of passing test cases out of 3 (0.0 to 1.0). **Note:** Missing test cases count as failures, matching `evaluation.py` behavior
- `hard_restriction`: 1 if all 3 test cases pass, 0 otherwise
- `messages`: Detailed messages for each test case

**Important:** Following `evaluation.py` logic, missing test case outputs are counted as failures. If you provide only 2 files and both pass, `soft_restriction = 2/3 = 0.67`, not 1.0.
