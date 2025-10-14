"""
Test script for the GCS-based evaluation endpoint.

This script tests that the endpoint can:
1. Successfully download a file from GCS
2. Parse the xlsx file
3. Return evaluation results

Potential issues to debug:
- GCS authentication (GOOGLE_ACCESS_KEY_ID, GOOGLE_ACCESS_KEY_SECRET)
- File not found in bucket
- Invalid xlsx file format
- Network connectivity
- Spreadsheet ID mismatch with dataset
"""

import requests
import sys
import os
import argparse
from dotenv import load_dotenv

load_dotenv()

def test_gcs_endpoint(api_url: str, spreadsheet_id: str, object_key: str):
    """
    Test the GCS evaluation endpoint.
    
    Args:
        api_url: The Modal endpoint URL
        spreadsheet_id: ID to use for evaluation (should exist in dataset)
        object_key: Path to file in GCS bucket (without bucket name)
    """
    
    print("=" * 80)
    print("GCS Endpoint Test")
    print("=" * 80)
    print(f"API URL: {api_url}")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Object Key: {object_key}")
    print(f"Bucket: shortcut_bg_task (hardcoded)")
    print("-" * 80)
    
    # Check environment variables
    print("\n1. Checking environment variables...")
    if os.getenv("GOOGLE_ACCESS_KEY_ID"):
        print("   ✓ GOOGLE_ACCESS_KEY_ID is set")
    else:
        print("   ✗ GOOGLE_ACCESS_KEY_ID is NOT set")
        print("   Note: Modal endpoint needs this in its environment")
    
    if os.getenv("GOOGLE_ACCESS_KEY_SECRET"):
        print("   ✓ GOOGLE_ACCESS_KEY_SECRET is set")
    else:
        print("   ✗ GOOGLE_ACCESS_KEY_SECRET is NOT set")
        print("   Note: Modal endpoint needs this in its environment")
    
    # Prepare request
    request_data = {
        "id": spreadsheet_id,
        "object_key": object_key,
    }
    
    print(f"\n2. Sending request to API...")
    print(f"   Request payload: {request_data}")
    
    try:
        response = requests.post(api_url, json=request_data, timeout=120)
        
        print(f"\n3. Response received")
        print(f"   Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ✗ HTTP Error")
            print(f"   Response body: {response.text}")
            return False
        
        result = response.json()
        
        print("\n4. Parsing response...")
        print(f"   Success: {result.get('success')}")
        
        if not result.get("success"):
            print(f"   ✗ Evaluation failed")
            print(f"   Error message: {result.get('message', 'No message')}")
            print(f"   ID: {result.get('id')}")
            
            # Debug hints
            print("\n   Debugging hints:")
            if "not found" in result.get('message', '').lower():
                print("   - File might not exist in GCS bucket")
                print("   - Check object_key path is correct")
                print("   - Verify bucket access permissions")
            elif "spreadsheet id" in result.get('message', '').lower():
                print("   - Spreadsheet ID not in dataset")
                print("   - Try a different ID like '17-35' or '19-7'")
            elif "decode" in result.get('message', '').lower() or "parse" in result.get('message', '').lower():
                print("   - File might be corrupted or not a valid xlsx")
                print("   - Check file format in GCS")
            elif "auth" in result.get('message', '').lower() or "credential" in result.get('message', '').lower():
                print("   - GCS authentication issue")
                print("   - Verify GOOGLE_ACCESS_KEY_ID and GOOGLE_ACCESS_KEY_SECRET in Modal environment")
            
            return False
        
        # Success case
        print(f"   ✓ Evaluation completed successfully!")
        print(f"\n5. Evaluation Results:")
        print(f"   ID: {result.get('id')}")
        print(f"   Instruction Type: {result.get('instruction_type')}")
        print(f"   Overall Result: {'PASS' if result.get('result') else 'FAIL'}")
        print(f"   Test Case Results: {result.get('test_case_results')}")
        print(f"   Soft Restriction: {result.get('soft_restriction', 0):.2%}")
        print(f"   Hard Restriction: {result.get('hard_restriction')}")
        
        print(f"\n   Messages:")
        for msg in result.get("messages", []):
            if msg:
                print(f"   - {msg}")
        
        # Validate we got expected data
        print(f"\n6. Validation:")
        checks = [
            ("ID returned", result.get('id') is not None),
            ("Instruction type returned", result.get('instruction_type') is not None),
            ("Test case results returned", result.get('test_case_results') is not None),
            ("At least one test case evaluated", result.get('test_case_results', [None])[0] is not None),
            (f"Soft restriction calculated: {result.get('soft_restriction')}", result.get('soft_restriction') is not None),
            (f"Hard restriction calculated: {result.get('hard_restriction')}", result.get('hard_restriction') is not None),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"   {status} {check_name}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print("\n" + "=" * 80)
            print("TEST PASSED: File successfully downloaded, parsed, and evaluated!")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("TEST INCOMPLETE: Some validations failed")
            print("=" * 80)
        
        return all_passed
        
    except requests.exceptions.Timeout:
        print(f"   ✗ Request timed out after 120 seconds")
        print(f"\n   Debugging hints:")
        print(f"   - File might be very large")
        print(f"   - GCS download might be slow")
        print(f"   - Increase timeout if needed")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"   ✗ Connection error: {str(e)}")
        print(f"\n   Debugging hints:")
        print(f"   - Check Modal endpoint URL is correct")
        print(f"   - Verify Modal app is deployed")
        print(f"   - Check network connectivity")
        return False
        
    except Exception as e:
        print(f"   ✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test the GCS-based spreadsheet evaluation endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python evaluation/test_gcp_endpoint.py \\
    --url https://your-app.modal.run/evaluate_spreadsheet_gcp \\
    --id 17-35 \\
    --object-key rl_env/test/spreadsheet_bench_17251/clearcut-00579e72
        """
    )
    
    parser.add_argument(
        "--url",
        required=True,
        help="Modal API endpoint URL for evaluate_spreadsheet_gcp"
    )
    
    parser.add_argument(
        "--id",
        dest="spreadsheet_id",
        default="17-35",
        help="Spreadsheet ID to use (default: 17-35)"
    )
    
    parser.add_argument(
        "--object-key",
        required=True,
        help="Object key in GCS bucket (path without bucket name)"
    )
    
    args = parser.parse_args()
    
    success = test_gcs_endpoint(args.url, args.spreadsheet_id, args.object_key)
    sys.exit(0 if success else 1)

