"""
Univer API Inference for SpreadsheetBench

This script provides an asynchronous inference client for running SpreadsheetBench tasks
through the Univer API. It supports concurrent task processing with slow-start concurrency
control to prevent API overload.

Usage:
    Basic usage:
        python inference_univer.py --dataset sample_data_200

    Command-line arguments:
        --dataset: Dataset name located in data/ directory (default: all_data_912_v0.1)
        --max_workers: Maximum concurrent tasks (default: 8)
        --endpoint: Univer API endpoint URL (default: https://bench.univer.plus)
        --startup_interval: Slow start interval in seconds (default: 0.5)

Environment Preparation:
    1. Install required dependencies:
        pip install httpx aiofiles tqdm

    2. Set environment variable (Required):
        export UNIVER_COOKIE="your_cookie_value"

    3. Ensure dataset structure (Required):
        The script expects datasets in the following structure:
        data/
        └── <dataset_name>/
            ├── dataset.json          # Task definitions
            └── <spreadsheet_path>/   # Input Excel files
                └── 1_<task_id>_input.xlsx

    4. Output structure:
        Results will be saved to (folder will be created if not exists):
        data/<dataset_name>/outputs/univer_univer/
        └── 1_<task_id>_output.xlsx
        
        Logs will be saved to:
        data/<dataset_name>/log/univer_univer.jsonl


Important Notes:
    1. Concurrency Control:
       - The script uses a slow-start mechanism that gradually increases concurrency
         from 1 to max_workers to prevent API overload
       - Adjust --max_workers based on API rate limits and server capacity
       - Default max_workers=8 is suitable for most use cases

    2. Timeouts:
       - Connection timeout: 60 seconds
       - Read timeout: 600 seconds (10 minutes) per request
       - Task polling: Up to 90 retries with 10-second intervals (15 minutes total)

    3. Error Handling:
       - Failed tasks are logged to the JSONL log file with error details
       - The script continues processing remaining tasks even if some fail
       - Check the log file for detailed error information

    4. API Requirements:
       - Requires valid Univer API endpoint access
       - Cookie authentication is required (via UNIVER_COOKIE env var)
       - API endpoint must support /arena-api/bench/run and /arena-api/bench/status endpoints

Example:
    # Process a sample dataset with 8 concurrent workers
    python inference_univer.py --dataset sample_data_200 --max_workers 8
"""

import os
import json
import argparse
import asyncio
import time
from typing import Dict, Any
from asyncio import Semaphore
from pathlib import Path

try:
    import httpx
    import aiofiles
    from tqdm.asyncio import tqdm as async_tqdm
except ImportError:
    print(f"❌ Missing required dependencies. Please run the following command to install:")
    print(f"   pip install httpx aiofiles tqdm")
    print(f"   or: python -m pip install httpx aiofiles tqdm")
    raise

class SlowStartController:
    """Slow start concurrency controller

    Controls concurrency through semaphore and gradually increases concurrency limit
    """

    def __init__(self, max_concurrency: int, startup_interval: float = 0.5):
        """
        Args:
            max_concurrency: Maximum concurrency limit
            startup_interval: Startup interval in seconds (default: increase by 1 every 0.5s)
        """
        self.max_concurrency = max_concurrency
        self.startup_interval = startup_interval
        self.semaphore = Semaphore(1)  # Initial concurrency is 1
        self.current_limit = 1
        self._startup_task = None
        self._is_running = False

    async def start(self):
        """Start the slow start process"""
        if not self._is_running:
            self._is_running = True
            self._startup_task = asyncio.create_task(self._gradual_increase())
            print(f"🚀 Slow start initiated, initial concurrency: {self.current_limit}, max concurrency: {self.max_concurrency}")

    async def _gradual_increase(self):
        """Gradually increase concurrency limit"""
        while self.current_limit < self.max_concurrency:
            await asyncio.sleep(self.startup_interval)
            self.current_limit += 1
            # Increase semaphore capacity
            self.semaphore._value += 1

    async def acquire(self):
        """Acquire execution permission"""
        await self.semaphore.acquire()

    def release(self):
        """Release execution permission"""
        self.semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()

    async def stop(self):
        """Stop slow start"""
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass


class AsyncTaskProcessor:
    """Async task processor

    Handles API calls, file downloads and other operations for individual tasks
    """

    def __init__(self, endpoint: str, univer_cookie: str | None = None):
        self.endpoint = endpoint
        self.session: httpx.AsyncClient = None
        self.cookie = univer_cookie or os.getenv('UNIVER_COOKIE')

    async def initialize(self):
        limits = httpx.Limits(
            max_keepalive_connections=200,  # Maximum keep-alive connections
            max_connections=200,  # Maximum connections
            keepalive_expiry=300.0  # Keep-alive expiry in seconds
        )

        timeout = httpx.Timeout(
            timeout=600.0,  # Total timeout: 10 minutes
            connect=60.0,   # Connection timeout: 1 minute
            read=600.0      # Read timeout: 10 minutes
        )

        self.session = httpx.AsyncClient(
            limits=limits,
            timeout=timeout
        )

    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()

    async def bench_run(self, input_file_path: str, task_data: Dict[str, Any]) -> Dict:
        try:
            async with aiofiles.open(input_file_path, 'rb') as f:
                file_content = await f.read()

            files = {
                'file': (
                    os.path.basename(input_file_path),
                    file_content,
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            }
            data = {
                'task': json.dumps(task_data),
            }

            headers = {
                'Cookie': self.cookie,
                'Accept': 'application/json'
            }

            # Send request to run benchmark
            response = await self.session.post(f"{self.endpoint}/arena-api/bench/run", data=data, files=files, headers=headers, timeout=600.0)
            if response.status_code != 200:
                raise Exception(f"Bench run failed: {response.status_code}, {response.text}")
            
            # Wait for results (max 90 x 10 seconds)
            run_id = response.json().get('runId')
            wait_for_results = 90
            for _ in range(wait_for_results):
                response = await self.session.get(f"{self.endpoint}/arena-api/bench/status/{run_id}", headers=headers, timeout=600.0)
                if response.status_code != 200:
                    raise Exception(f"Get status failed: {response.status_code}, {response.text}, task: {run_id}")

                response_json = response.json()
                if response_json.get('status') == 'completed':
                    # task completed successfully, get fileUrl
                    file_url = response_json.get('fileUrl')
                    if file_url:
                        return {
                            "error": {"code": 1, "message": "success"},
                            "fileUrl": file_url
                        }
                    else:
                        raise Exception(f"Task {run_id} completed but missing fileUrl: {json.dumps(response_json, ensure_ascii=False)}")
                elif response_json.get('status') in ['running', 'created']:
                    # task not completed yet, wait for 10 seconds and check again
                    await asyncio.sleep(10)
                    continue
                else:
                    # unknown status, raise error
                    raise Exception(f"Task {run_id} unknown status: {response_json.get('status')}")
            # not completed after max retries, raise error
            raise Exception(f"Task {run_id} not completed after {wait_for_results} retries")

        except asyncio.TimeoutError:
            # timeout, raise error
            raise Exception(f"Task {run_id} timeout")
        except Exception as e:
            raise Exception(f"Task {run_id} failed: {str(e)}")

    async def download_file(self, file_url: str, output_path: str):
        try:
            async with self.session.stream("GET", file_url) as response:
                if response.status_code == 200:
                    async with aiofiles.open(output_path, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            await f.write(chunk)
                else:
                    raise Exception(f"Download failed: status {response.status_code}")
        except asyncio.TimeoutError:
            raise Exception("File download timeout")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    async def process_task(
        self,
        task: Dict,
        dataset_path: str,
        output_folder: str,
        test_case_idx: int = 1
    ) -> Dict:
        """Process a single task

        Args:
            task: Task data
            dataset_path: Dataset path
            output_folder: Output folder
            test_case_idx: Test case index (default: 1)

        Returns:
            dict: Processing result
        """
        task_id = task['id']
        result = {
            'id': task_id,
            'success': False,
            'error': None,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        try:
            # Prepare input file
            file_name = f"{test_case_idx}_{task_id}_input.xlsx"
            input_file_path = f"{dataset_path}/{task['spreadsheet_path']}/{file_name}"

            if not os.path.exists(input_file_path):
                raise FileNotFoundError(f"Input file not found: {input_file_path}")

            # Run task
            api_result = await self.bench_run(input_file_path, task)
            if api_result.get('error', {}).get('code') != 1:
                error_msg = api_result.get('error', {}).get('message', 'Unknown error')
                raise Exception(f"API Error: {error_msg}")

            # Download result file
            file_url = api_result['fileUrl']
            output_file_name = f"{test_case_idx}_{task_id}_output.xlsx"
            output_file_path = f"{output_folder}/{output_file_name}"
            await self.download_file(file_url, output_file_path)

            result['success'] = True
            return result

        except Exception as e:
            result['error'] = str(e)
            return result


async def gen_solution_async(opt, univer_cookie: str):
    """Async main processing function

    Args:
        opt: Command line arguments object
    """
    # Read dataset
    dataset_dir = Path(__file__).parent.parent / 'data' / opt.dataset
    dataset_json_path = dataset_dir / 'dataset.json'
    dataset = json.loads(dataset_json_path.read_text(encoding='utf-8'))

    # Create output folder
    output_folder = dataset_dir / 'outputs' / f'univer_{opt.model}'
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output folder: {output_folder}")

    # Create log folder
    log_folder = dataset_dir / 'log'
    log_folder.mkdir(parents=True, exist_ok=True)

    # Initialize processor and controller
    processor = AsyncTaskProcessor(opt.endpoint, univer_cookie)
    await processor.initialize()

    controller = SlowStartController(
        max_concurrency=opt.max_workers,
        startup_interval=opt.startup_interval
    )
    await controller.start()

    # Statistics
    stats = {
        'total': len(dataset),
        'success': 0,
        'failed': 0,
        'errors': [],
        'start_time': time.time()
    }

    # Create progress bar
    pbar = async_tqdm(
        total=len(dataset),
        desc="Processing tasks",
        unit="task",
        colour="green"
    )

    async def process_with_limit(task):
        """Task processing with concurrency limit"""
        async with controller:  # Auto acquire and release semaphore
            result = await processor.process_task(
                task, dataset_dir, output_folder
            )

            # Update statistics
            if result['success']:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(result)

            log_file = log_folder / f'univer_{opt.model}.jsonl'
            try:
                async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                    await f.write(json.dumps(result, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"⚠️  Warning: Failed to write log entry for task {result.get('id', 'unknown')}: {e}")

            # Update progress bar
            pbar.update(1)
            success_rate = (stats['success'] / (stats['success'] + stats['failed']) * 100) if (stats['success'] + stats['failed']) > 0 else 0
            pbar.set_postfix({
                'Success': stats['success'],
                'Failed': stats['failed'],
                'Rate': f'{success_rate:.1f}%',
                'Concur': controller.current_limit
            })

            return result

    try:
        # Execute all tasks concurrently
        tasks = [process_with_limit(task) for task in dataset]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    finally:
        pbar.close()
        await controller.stop()
        await processor.session.aclose()

    # Calculate elapsed time
    elapsed_time = time.time() - stats['start_time']

    # Output statistics
    print(f"\n" + "=" * 60)
    print(f"📊 Processing Completed")
    print(f"=" * 60)
    print(f"   Total tasks: {stats['total']}")
    print(f"   Successful: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"   Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"   Total time: {elapsed_time:.2f} seconds")
    print(f"   Avg speed: {stats['total']/elapsed_time:.2f} tasks/sec")
    print(f"   Output folder: {output_folder}")
    print(f"   Log file: {log_folder}/univer_{opt.model}.jsonl")

    print("=" * 60)


def gen_solution(opt, univer_cookie: str):
    """Sync entry point (compatible with original calling method)"""
    asyncio.run(gen_solution_async(opt, univer_cookie))


def parse_option():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Univer API inference for SpreadsheetBench (Async Version)"
    )

    # Basic parameters
    parser.add_argument('--model', type=str, default='univer',
                       help='Model name for output folder naming (default: univer)')
    parser.add_argument('--dataset', type=str, default="all_data_912_v0.1",
                       help='Dataset name (default: all_data_912_v0.1)')
    parser.add_argument('--endpoint', type=str, default="https://bench.univer.plus",
                       help='Univer API endpoint')
    # Concurrency control parameters
    parser.add_argument('--max_workers', type=int, default=8,
                       help='Maximum concurrent tasks (default: 8)')
    parser.add_argument('--startup_interval', type=float, default=0.5,
                       help='Slow start interval in seconds (default: 0.5, i.e., increase by 1 every 0.5s)')

    opt = parser.parse_args()
    return opt


if __name__ == '__main__':
    opt = parse_option()

    univer_cookie = os.getenv('UNIVER_COOKIE') or "_univer=LFMVIULEJZVVUVDIGJSVQ4SQNI3EMM2CJRIXC"

    print("=" * 60)
    print("🚀 Univer Inference for SpreadsheetBench")
    print("=" * 60)
    print(f"📌 Inference Provider: Univer")
    print(f"📌 Dataset: {opt.dataset}")
    print(f"📌 Endpoint: {opt.endpoint}")
    print(f"📌 Max workers: {opt.max_workers}")
    print("=" * 60)
    print()

    gen_solution(opt, univer_cookie)
