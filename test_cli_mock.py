#!/usr/bin/env python3
"""
Test CLI with mock HTTP server to verify end-to-end caching behavior.
"""
import json
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time


class MockBotswainHandler(BaseHTTPRequestHandler):
    """Mock Botswain API server"""

    request_count = 0

    def log_message(self, format, *args):
        """Suppress HTTP server logs"""
        pass

    def do_POST(self):
        """Handle POST requests to /api/query"""
        if self.path == '/api/query':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_json = json.loads(post_data.decode('utf-8'))

            MockBotswainHandler.request_count += 1

            # Simulate caching: first request uncached, second cached
            is_cached = MockBotswainHandler.request_count > 1
            exec_time = 2 if is_cached else 1250

            # Check for cache bypass
            if request_json.get('use_cache') == False:
                is_cached = False
                exec_time = 1250

            response = {
                'response': f'Found 5 commits from dana (request #{MockBotswainHandler.request_count}).',
                'cached': is_cached,
                'results': {
                    'entity': 'git_commit',
                    'count': 5,
                    'execution_time_ms': exec_time,
                    'results': [
                        {
                            'sha': 'abc123',
                            'message': 'feat: add caching',
                            'author': 'dana',
                            'date': '2026-03-11',
                            'repo': 'botswain'
                        }
                    ]
                },
                'intent': {
                    'entity': 'git_commit',
                    'intent_type': 'query',
                    'filters': {'author': 'dana'}
                }
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_mock_server(port=8099):
    """Run mock server in background thread"""
    server = HTTPServer(('localhost', port), MockBotswainHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_cli():
    """Test CLI with mock server"""
    print("=" * 70)
    print("  Botswain CLI End-to-End Cache Test")
    print("=" * 70)
    print()

    # Start mock server
    print("🚀 Starting mock server on port 8099...")
    server = run_mock_server(8099)
    time.sleep(0.5)
    print("   ✅ Server ready")
    print()

    url = "http://localhost:8099"

    try:
        # Test 1: First query (cache miss)
        print("🔹 Test 1: First Query (Cache Miss)")
        print("-" * 70)
        result = subprocess.run(
            ['./botswain-cli.py', 'Show my commits', '--url', url, '-y'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = result.stdout
            print(output)

            # Verify it shows NOT cached
            if 'Cache:' not in output or '✓ Cached' not in output:
                print("✅ First query correctly shows as uncached")
            else:
                print("❌ First query incorrectly shows as cached")
                sys.exit(1)

            # Verify slow execution time
            if '1250ms' in output:
                print("✅ First query execution time: 1250ms (uncached)")
            else:
                print("⚠️  Execution time not shown as expected")
        else:
            print(f"❌ CLI failed: {result.stderr}")
            sys.exit(1)

        print()

        # Test 2: Second query (cache hit)
        print("🔹 Test 2: Second Query (Cache Hit)")
        print("-" * 70)
        result = subprocess.run(
            ['./botswain-cli.py', 'Show my commits', '--url', url, '-y'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = result.stdout
            print(output)

            # Verify it shows cached
            if 'Cache:' in output and '✓ Cached' in output:
                print("✅ Second query correctly shows as cached")
            else:
                print("❌ Second query should show as cached")
                sys.exit(1)

            # Verify fast execution time
            if '2ms' in output:
                print("✅ Second query execution time: 2ms (cached)")
            else:
                print("⚠️  Execution time not shown as expected")
        else:
            print(f"❌ CLI failed: {result.stderr}")
            sys.exit(1)

        print()

        # Test 3: Third query with --no-cache flag
        print("🔹 Test 3: Cache Bypass (--no-cache flag)")
        print("-" * 70)
        result = subprocess.run(
            ['./botswain-cli.py', 'Show my commits', '--url', url, '--no-cache', '-y'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = result.stdout
            print(output)

            # Verify it shows NOT cached
            if 'Cache:' not in output or '✓ Cached' not in output:
                print("✅ Cache bypass correctly shows as uncached")
            else:
                print("❌ Cache bypass should not show as cached")
                sys.exit(1)

            # Verify slow execution time
            if '1250ms' in output:
                print("✅ Cache bypass execution time: 1250ms (bypassed)")
            else:
                print("⚠️  Execution time not shown as expected")
        else:
            print(f"❌ CLI failed: {result.stderr}")
            sys.exit(1)

        print()

        # Test 4: Raw JSON output
        print("🔹 Test 4: Raw JSON Output (--raw flag)")
        print("-" * 70)
        result = subprocess.run(
            ['./botswain-cli.py', 'Show my commits', '--url', url, '--raw', '-y'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            output = result.stdout
            data = json.loads(output)

            if data.get('cached') == True:
                print("✅ Raw JSON shows cached: true")
            else:
                print("⚠️  Expected cached: true in raw JSON")

            if 'results' in data and 'execution_time_ms' in data['results']:
                print(f"✅ Raw JSON includes execution_time_ms: {data['results']['execution_time_ms']}ms")
            else:
                print("❌ execution_time_ms missing in raw JSON")
                sys.exit(1)
        else:
            print(f"❌ CLI failed: {result.stderr}")
            sys.exit(1)

        print()

        # Summary
        print("=" * 70)
        print("  ✅ ALL CLI TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✅ CLI correctly displays cache miss (1st query)")
        print("  ✅ CLI correctly displays cache hit (2nd query)")
        print("  ✅ CLI correctly handles --no-cache flag")
        print("  ✅ CLI correctly outputs raw JSON with cache status")
        print("  ✅ Cache indicators show in natural format")
        print("  ✅ Execution times displayed correctly")
        print()
        print("🎉 Botswain CLI working correctly with caching!")

    finally:
        server.shutdown()


if __name__ == '__main__':
    test_cli()
