#!/usr/bin/env python3
"""
Botswain CLI - Command-line interface for natural language factory queries.

Usage:
    ./botswain-cli.py "What synthesizers are available?"
    ./botswain-cli.py "Show me online instruments" --format json
    ./botswain-cli.py "List all synthesizers" --url http://localhost:8002
    ./botswain-cli.py "Show orders" --page 2 --page-size 25
    ./botswain-cli.py "Show orders" --offset 50 --limit 25
"""

import argparse
import json
import sys
import requests


def main():
    parser = argparse.ArgumentParser(
        description='Botswain CLI - Natural language factory query assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "What synthesizers are available?"
  %(prog)s "Show me online instruments" --format json
  %(prog)s "List all synthesizers" --url http://production:8002
  %(prog)s "Show orders" --page 2 --page-size 25
  %(prog)s "Show orders" --offset 50 --limit 25
        """
    )

    parser.add_argument(
        'question',
        help='Natural language question to ask'
    )

    parser.add_argument(
        '--format',
        choices=['natural', 'json', 'table'],
        default='natural',
        help='Response format (default: natural)'
    )

    parser.add_argument(
        '--url',
        default='http://localhost:8002',
        help='Botswain API base URL (default: http://localhost:8002)'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable query caching'
    )

    parser.add_argument(
        '--raw',
        action='store_true',
        help='Show raw JSON response'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show debug information'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed results (raw data from query)'
    )

    parser.add_argument(
        '--no-limit',
        action='store_true',
        help='Remove result limit (return all results)'
    )

    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip interactive prompts (auto-accept limit removal)'
    )

    # Pagination parameters
    parser.add_argument(
        '--page',
        type=int,
        help='Page number (1-indexed, default: 1)'
    )

    parser.add_argument(
        '--page-size',
        type=int,
        help='Results per page (default: 100, max: 1000)'
    )

    parser.add_argument(
        '--offset',
        type=int,
        help='Number of results to skip (default: 0)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum results to return (default: 100, max: 1000)'
    )

    args = parser.parse_args()

    # Build initial request to get intent
    api_url = f"{args.url.rstrip('/')}/api/query"
    payload = {
        'question': args.question,
        'format': args.format,
        'use_cache': not args.no_cache
    }

    # Add pagination parameters if provided
    if args.page is not None:
        payload['page'] = args.page
    if args.page_size is not None:
        payload['page_size'] = args.page_size
    if args.offset is not None:
        payload['offset'] = args.offset
    if args.limit is not None:
        payload['limit'] = args.limit

    if args.debug:
        print(f"[DEBUG] API URL: {api_url}", file=sys.stderr)
        print(f"[DEBUG] Initial Payload: {json.dumps(payload, indent=2)}", file=sys.stderr)
        print("", file=sys.stderr)

    # First, parse intent to check for limits (without executing full query)
    # For now, we'll just make the full request and check in one go
    # A future enhancement would be a separate /api/parse-intent endpoint

    try:
        # Interactive limit check (unless --no-limit)
        should_remove_limit = args.no_limit

        if not should_remove_limit:
            # Check if question suggests user wants all results
            all_keywords = ['all', 'every', 'which', 'what', 'list', 'show']
            question_lower = args.question.lower()
            suggests_all = any(kw in question_lower for kw in all_keywords)

            if suggests_all:
                if args.yes:
                    # Auto-accept with -y flag
                    should_remove_limit = True
                else:
                    # Interactive prompt
                    print("⚠️  Query Limit Notice", file=sys.stderr)
                    print("   This query will be limited to 10 results by default.", file=sys.stderr)
                    print("   Reason: Limits reduce cost and improve response time.", file=sys.stderr)
                    print("", file=sys.stderr)
                    response = input("   Remove limit and show all results? (y/N): ").strip().lower()
                    should_remove_limit = response == 'y'
                    print("", file=sys.stderr)

        # Add limit override to payload if needed
        if should_remove_limit:
            payload['override_limit'] = 1000  # Set high limit (max allowed)
            if args.debug:
                print(f"[DEBUG] Limit override applied: 1000", file=sys.stderr)

        # Make request
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60 if should_remove_limit else 30
        )

        if args.debug:
            print(f"[DEBUG] Status Code: {response.status_code}", file=sys.stderr)
            print("", file=sys.stderr)

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to Botswain API at {api_url}", file=sys.stderr)
        print(f"   Make sure the server is running: make run", file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.Timeout:
        print(f"❌ Error: Request timed out", file=sys.stderr)
        sys.exit(1)

    except requests.exceptions.HTTPError as e:
        print(f"❌ Error: HTTP {response.status_code}", file=sys.stderr)
        try:
            error_data = response.json()
            if 'error' in error_data:
                print(f"   {error_data['error']}", file=sys.stderr)
            else:
                print(f"   {json.dumps(error_data, indent=2)}", file=sys.stderr)
        except:
            print(f"   {response.text}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Display response
    if args.raw:
        print(json.dumps(data, indent=2))
    else:
        display_response(data, debug=args.debug, verbose=args.verbose)


def display_response(data, debug=False, verbose=False):
    """Display formatted response."""

    # Check for errors
    if 'error' in data:
        print(f"❌ Error: {data['error']}")
        if 'type' in data:
            print(f"   Type: {data['type']}")
        return

    # Main response
    print("📊 Query Results")
    print("=" * 60)
    print()

    if 'response' in data:
        print(data['response'])
        print()

    # Metadata
    if debug or 'results' in data:
        results = data.get('results', {})

        print("─" * 60)
        print(f"Entity:         {results.get('entity', 'N/A')}")
        print(f"Results Count:  {results.get('count', 0)}")
        print(f"Execution Time: {results.get('execution_time_ms', 0)}ms")

        if data.get('cached'):
            print("Cache:          ✓ Cached result")

        # Pagination info
        if 'pagination' in data:
            pagination = data['pagination']
            print("─" * 60)
            print("Pagination:")
            print(f"  Page:           {pagination.get('current_page', 1)} of {pagination.get('estimated_total_pages', '?')}")
            print(f"  Results:        {pagination.get('offset', 0) + 1}-{pagination.get('offset', 0) + results.get('count', 0)}")
            print(f"  Total:          {pagination.get('estimated_total', '?')}")
            if pagination.get('has_previous'):
                print(f"  Previous:       --page {pagination.get('previous_page')}")
            if pagination.get('has_next'):
                print(f"  Next:           --page {pagination.get('next_page')}")

        print()

    # Intent (debug mode)
    if debug and 'intent' in data:
        print("─" * 60)
        print("Intent:")
        print(json.dumps(data['intent'], indent=2))
        print()

    # Raw results (only in verbose mode)
    if verbose and 'results' in data and data['results'].get('results'):
        results_list = data['results']['results']
        if results_list and isinstance(results_list, list):
            print("─" * 60)
            print(f"Detailed Results ({len(results_list)} items):")
            print()
            for i, result in enumerate(results_list[:10], 1):  # Show first 10
                print(f"{i}. {json.dumps(result, indent=2)}")

            if len(results_list) > 10:
                print(f"\n... and {len(results_list) - 10} more")
            print()


if __name__ == '__main__':
    main()
