"""Load testing script for Sales Roleplay Chatbot API

Usage:
    python tests/load_test.py --url https://your-render-app.onrender.com --users 10 --duration 60

Options:
    --url URL           Base URL of deployed application (default: http://localhost:5000)
    --users N           Number of concurrent users (default: 5)
    --duration SECONDS  Test duration in seconds (default: 30)
    --ramp-up SECONDS   Ramp-up time to spawn all users (default: 5)
"""

import argparse
import time
import random
import threading
import statistics
import sys
from collections import defaultdict
from datetime import datetime
import requests


# ====================================================================
# Configuration & Test Data
# ====================================================================

TEST_MESSAGES = [
    "Hi, I'm looking for a car",
    "I need something fuel efficient",
    "What about safety features?",
    "I'm worried about the price",
    "Let me think about it",
    "Tell me more about the warranty",
    "How does it compare to competitors?",
    "I need to discuss with my partner",
    "What's the best you can do on price?",
    "Okay, I'm interested"
]

PRODUCT_QUERIES = [
    "Show me your electric cars",
    "I want a family SUV",
    "Looking for something sporty",
    "Need a reliable sedan",
    "What do you have in my budget?"
]


# ====================================================================
# Load Test Runner
# ====================================================================

class LoadTestMetrics:
    """Thread-safe metrics collector"""

    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = []
        self.status_codes = defaultdict(int)
        self.errors = []
        self.requests_sent = 0
        self.requests_completed = 0

    def record_request(self, status_code: int, response_time: float, error: str = None):
        with self.lock:
            self.requests_completed += 1
            self.status_codes[status_code] += 1
            if error:
                self.errors.append(error)
            else:
                self.response_times.append(response_time)

    def increment_sent(self):
        with self.lock:
            self.requests_sent += 1

    def get_summary(self):
        with self.lock:
            sorted_times = sorted(self.response_times) if self.response_times else []
            return {
                "total_requests": self.requests_sent,
                "completed": self.requests_completed,
                "successful": len(self.response_times),
                "failed": len(self.errors),
                "error_rate": len(self.errors) / self.requests_completed if self.requests_completed > 0 else 0,
                "response_time_avg": statistics.mean(self.response_times) if self.response_times else 0,
                "response_time_median": statistics.median(self.response_times) if self.response_times else 0,
                "response_time_p95": sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0,
                "response_time_min": min(self.response_times) if self.response_times else 0,
                "response_time_max": max(self.response_times) if self.response_times else 0,
                "status_codes": dict(self.status_codes),
                "sample_errors": self.errors[:5]
            }


class VirtualUser:
    """Simulates a single user interacting with the chatbot"""

    def __init__(self, user_id: int, base_url: str, metrics: LoadTestMetrics):
        self.user_id = user_id
        self.base_url = base_url.rstrip('/')
        self.metrics = metrics
        self.session = requests.Session()
        self.session_id = None
        self.running = False

    def start_session(self):
        """Initialize a new chat session"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/init",
                json={},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id")
                return True
        except Exception as e:
            self.metrics.record_request(0, 0, f"Session start failed: {str(e)}")
        return False

    def send_message(self, message: str):
        """Send a chat message and record metrics"""
        if not self.session_id:
            return

        self.metrics.increment_sent()
        start_time = time.time()

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json={"message": message},
                headers={"X-Session-ID": self.session_id},
                timeout=30
            )

            response_time = (time.time() - start_time) * 1000  # ms

            if response.status_code == 200:
                self.metrics.record_request(200, response_time)
            else:
                self.metrics.record_request(
                    response.status_code,
                    response_time,
                    f"HTTP {response.status_code}"
                )

        except requests.exceptions.Timeout:
            self.metrics.record_request(0, 0, "Timeout")
        except requests.exceptions.ConnectionError:
            self.metrics.record_request(0, 0, "Connection failed")
        except Exception as e:
            self.metrics.record_request(0, 0, str(e))

    def run(self, duration: float):
        """Run user simulation for specified duration"""
        self.running = True

        if not self.start_session():
            print(f"[User {self.user_id}] Failed to start session")
            return

        print(f"[User {self.user_id}] Session started: {self.session_id}")

        end_time = time.time() + duration
        message_count = 0

        while self.running and time.time() < end_time:
            # Simulate natural conversation pace (2-8 seconds between messages)
            time.sleep(random.uniform(2, 8))

            # Alternate between product queries and follow-up messages
            if message_count % 5 == 0:
                message = random.choice(PRODUCT_QUERIES)
            else:
                message = random.choice(TEST_MESSAGES)

            self.send_message(message)
            message_count += 1

        print(f"[User {self.user_id}] Completed {message_count} messages")

    def stop(self):
        """Signal the user to stop"""
        self.running = False


def run_load_test(base_url: str, num_users: int, duration: int, ramp_up: int):
    """Execute load test with specified parameters"""

    print("\n" + "="*70)
    print("LOAD TEST CONFIGURATION")
    print("="*70)
    print(f"Target URL:       {base_url}")
    print(f"Concurrent Users: {num_users}")
    print(f"Test Duration:    {duration}s")
    print(f"Ramp-up Time:     {ramp_up}s")
    print(f"Start Time:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Health check (skipped - not critical)
    print("Starting load test...\n")

    metrics = LoadTestMetrics()
    users = []
    threads = []

    # Spawn users with ramp-up
    spawn_delay = ramp_up / num_users if num_users > 1 else 0

    for i in range(num_users):
        user = VirtualUser(i + 1, base_url, metrics)
        users.append(user)

        thread = threading.Thread(target=user.run, args=(duration,))
        threads.append(thread)
        thread.start()

        if i < num_users - 1:  # Don't sleep after last user
            time.sleep(spawn_delay)

    print(f"[SPAWNED] All {num_users} users spawned\n")

    # Monitor progress
    start_time = time.time()
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        elapsed = time.time() - start_time
        summary = metrics.get_summary()
        print(f"[{elapsed:.0f}s] Requests: {summary['completed']} | "
              f"Avg Response: {summary.get('response_time_avg', 0):.0f}ms | "
              f"Errors: {summary.get('failed', summary.get('errors', 0))}")

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    return metrics


# ====================================================================
# Results Display
# ====================================================================

def print_results(metrics: LoadTestMetrics, duration: int):
    """Display formatted test results"""
    summary = metrics.get_summary()

    print("\n" + "="*70)
    print("LOAD TEST RESULTS")
    print("="*70)

    print("\n[STATS] Request Statistics:")
    print(f"   Total Sent:       {summary['total_requests']}")
    print(f"   Completed:        {summary['completed']}")
    print(f"   Successful:       {summary['successful']}")
    print(f"   Failed:           {summary['failed']}")
    print(f"   Error Rate:       {summary['error_rate']*100:.1f}%")

    if summary['successful'] > 0:
        print("\n Response Times (ms):")
        print(f"   Average:          {summary['response_time_avg']:.2f}")
        print(f"   Median:           {summary['response_time_median']:.2f}")
        print(f"   95th Percentile:  {summary['response_time_p95']:.2f}")
        print(f"   Min:              {summary['response_time_min']:.2f}")
        print(f"   Max:              {summary['response_time_max']:.2f}")

    print("\n Throughput:")
    print(f"   Requests/sec:     {summary['completed'] / duration:.2f}")

    print("\n Status Codes:")
    for code, count in sorted(summary['status_codes'].items()):
        print(f"   {code}: {count}")

    if summary['sample_errors']:
        print("\n Sample Errors:")
        for error in summary['sample_errors']:
            print(f"   - {error}")

    print("\n" + "="*70)

    # Pass/fail criteria
    if summary['error_rate'] > 0.1:  # >10% error rate
        print(" TEST FAILED: Error rate exceeds 10%")
        return False
    elif summary.get('response_time_p95', 0) > 5000:  # >5s p95
        print(" WARNING: 95th percentile response time exceeds 5s")
        print("[PASS] TEST PASSED (with warnings)")
        return True
    else:
        print(" TEST PASSED")
        return True


# ====================================================================
# CLI Entry Point
# ====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Load test the Sales Roleplay Chatbot API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--url",
        default="http://localhost:5000",
        help="Base URL of the application (default: http://localhost:5000)"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=5,
        help="Number of concurrent users (default: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--ramp-up",
        type=int,
        default=5,
        help="Ramp-up time in seconds (default: 5)"
    )

    args = parser.parse_args()

    try:
        metrics = run_load_test(
            base_url=args.url,
            num_users=args.users,
            duration=args.duration,
            ramp_up=args.ramp_up
        )

        success = print_results(metrics, args.duration)
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n Test interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
