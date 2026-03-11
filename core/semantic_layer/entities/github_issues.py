"""
GitHub Issues entity for querying issues and pull requests.
Uses GitHub GraphQL API for fast queries, with gh CLI fallback.

SECURITY: Restricted to Synthego organization repositories only.
"""
import json
import os
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base import BaseEntity


class GitHubIssuesEntity(BaseEntity):
    """
    Queries GitHub issues and pull requests using GraphQL API (primary) or gh CLI (fallback).

    SECURITY RESTRICTIONS:
    - READ-ONLY access via GraphQL API / gh CLI
    - Limited to Synthego organization repositories only
    - No write operations allowed
    """

    name = "github_issue"
    description = "GitHub issues and pull requests (bugs, features, tasks, code reviews) from Synthego repositories. Use for questions about development work, bug tracking, PR status."

    # Allowed GitHub organization
    ALLOWED_ORG = "Synthego"

    # GitHub GraphQL endpoint
    GRAPHQL_URL = "https://api.github.com/graphql"

    def _get_github_token(self) -> Optional[str]:
        """
        Get GitHub token from environment or gh CLI.

        Returns:
            GitHub token or None if unavailable
        """
        # Try environment variable first
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            return token

        # Try to get from gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        return None

    def _validate_repo(self, repo: str) -> bool:
        """
        Validate that repo belongs to Synthego organization.

        Args:
            repo: Repository in format "owner/repo"

        Returns:
            True if repo is from Synthego org, False otherwise
        """
        if not repo:
            return False

        # Check format
        if "/" not in repo:
            return False

        owner, _ = repo.split("/", 1)

        # Only allow Synthego organization
        return owner == self.ALLOWED_ORG

    def _get_current_repo(self) -> str:
        """
        Try to detect the current repository from git remote (READ-ONLY).
        Returns repo in format "owner/repo" or empty string if not found.

        SECURITY: Only uses read-only git commands (git remote get-url)
        """
        try:
            # READ-ONLY git command
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd="."  # Explicitly set working directory
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse various git URL formats
                # https://github.com/owner/repo.git
                # git@github.com:owner/repo.git
                if "github.com" in url:
                    if ":" in url and not url.startswith("http"):
                        # SSH format
                        parts = url.split(":")[-1].replace(".git", "")
                    else:
                        # HTTPS format
                        parts = url.split("github.com/")[-1].replace(".git", "")

                    repo = parts.strip()

                    # Validate it's a Synthego repo
                    if self._validate_repo(repo):
                        return repo
        except:
            pass
        return ""

    # Default repos to search when no specific repo is mentioned
    DEFAULT_REPOS = [
        "Synthego/barb",
        "Synthego/buckaneer",
        "Synthego/kraken",
        "Synthego/galleon",
        "Synthego/hook",
        "Synthego/line",
        "Synthego/sos",
    ]

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get issues from GitHub using GraphQL API (preferred) or gh CLI (fallback).

        Returns a list of dicts (not a Django queryset) since GitHub is an API.

        SECURITY: All operations are read-only. No modifications to GitHub data.
        """
        # Determine which repo(s) to query
        repos = []
        if filters and 'repo' in filters:
            repo_value = filters['repo']

            # Handle "default" keyword - search across key repos
            if repo_value == "default":
                repos = self.DEFAULT_REPOS
            # Handle comma-separated list
            elif ',' in repo_value:
                repos = [r.strip() for r in repo_value.split(',')]
            else:
                repos = [repo_value]
        else:
            # No repo specified - try to detect current repo
            current_repo = self._get_current_repo()
            if current_repo:
                repos = [current_repo]
            else:
                # Fall back to default repos
                repos = self.DEFAULT_REPOS

        # SECURITY: Validate all repos are from Synthego organization
        valid_repos = [r for r in repos if self._validate_repo(r)]
        if not valid_repos:
            # If no valid Synthego repos, return empty results
            return []

        # Try GraphQL first (much faster for multi-repo)
        token = self._get_github_token()
        if token and len(valid_repos) > 1:
            # Use GraphQL for multi-repo queries (5x faster)
            try:
                return self._query_graphql(valid_repos, filters, token)
            except Exception:
                # Fall back to gh CLI if GraphQL fails
                pass

        # Fallback to gh CLI (one repo at a time)
        all_issues = []
        for repo in valid_repos:
            issues = self._query_single_repo(repo, filters)
            all_issues.extend(issues)

        return all_issues

    def _query_graphql(self, repos: List[str], filters: Dict[str, Any], token: str) -> List[Dict[str, Any]]:
        """
        Query GitHub using GraphQL API (single request for all repos).

        Args:
            repos: List of repositories in format "owner/repo"
            filters: Query filters
            token: GitHub API token

        Returns:
            List of issue dicts
        """
        import requests

        # Build search query
        search_parts = [f"org:{self.ALLOWED_ORG}"]

        # Add repo filter if specific repos requested (not all)
        if repos != self.DEFAULT_REPOS:
            repo_queries = " ".join([f"repo:{repo}" for repo in repos])
            search_parts.append(f"({repo_queries})")

        # State filter
        if filters and 'state' in filters:
            state = filters['state'].lower()
            if state == 'open':
                search_parts.append("is:open")
            elif state == 'closed':
                search_parts.append("is:closed")
            # 'all' = no filter

        # Issue vs PR type
        if filters and filters.get('type') == 'pr':
            search_parts.append("is:pr")
        else:
            search_parts.append("is:issue")

        # Assignee filter
        if filters and 'assignee' in filters:
            search_parts.append(f"assignee:{filters['assignee']}")

        # Author filter
        if filters and 'author' in filters:
            search_parts.append(f"author:{filters['author']}")

        # Label filter
        if filters and 'label' in filters:
            search_parts.append(f"label:{filters['label']}")

        # Search text filter
        if filters and 'search' in filters:
            search_parts.append(f"{filters['search']} in:title,body")

        # Date filters
        if filters and 'created_after' in filters:
            date_value = self._parse_date_filter(filters['created_after'])
            search_parts.append(f"created:>={date_value.strftime('%Y-%m-%d')}")

        if filters and 'updated_after' in filters:
            date_value = self._parse_date_filter(filters['updated_after'])
            search_parts.append(f"updated:>={date_value.strftime('%Y-%m-%d')}")

        search_query = " ".join(search_parts)

        # GraphQL query
        query = """
        query($searchQuery: String!, $first: Int!) {
          search(query: $searchQuery, type: ISSUE, first: $first) {
            issueCount
            nodes {
              ... on Issue {
                number
                title
                state
                author {
                  login
                }
                labels(first: 10) {
                  nodes {
                    name
                  }
                }
                assignees(first: 10) {
                  nodes {
                    login
                  }
                }
                createdAt
                updatedAt
                closedAt
                url
                body
                repository {
                  nameWithOwner
                }
              }
              ... on PullRequest {
                number
                title
                state
                author {
                  login
                }
                labels(first: 10) {
                  nodes {
                    name
                  }
                }
                assignees(first: 10) {
                  nodes {
                    login
                  }
                }
                createdAt
                updatedAt
                closedAt
                url
                body
                repository {
                  nameWithOwner
                }
              }
            }
          }
        }
        """

        # Execute GraphQL request
        response = requests.post(
            self.GRAPHQL_URL,
            json={
                'query': query,
                'variables': {
                    'searchQuery': search_query,
                    'first': 100
                }
            },
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        # Parse results into our format
        issues = []
        for node in data['data']['search']['nodes']:
            if node is None:
                continue

            # Extract author
            author = node.get('author', {})
            author_login = author.get('login') if author else None

            # Extract labels
            labels_data = node.get('labels', {}).get('nodes', [])
            labels = [label['name'] for label in labels_data if label]

            # Extract assignees
            assignees_data = node.get('assignees', {}).get('nodes', [])
            assignees = [assignee['login'] for assignee in assignees_data if assignee]

            issues.append({
                'number': node.get('number'),
                'title': node.get('title'),
                'state': node.get('state', '').upper(),  # OPEN/CLOSED
                'author': {'login': author_login} if author_login else None,
                'labels': [{'name': name} for name in labels],
                'assignees': [{'login': login} for login in assignees],
                'createdAt': node.get('createdAt'),
                'updatedAt': node.get('updatedAt'),
                'closedAt': node.get('closedAt'),
                'url': node.get('url'),
                'body': node.get('body'),
                'repo': node.get('repository', {}).get('nameWithOwner')
            })

        return issues

    def _query_single_repo(self, repo: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query a single repository for issues using gh CLI (fallback).

        Args:
            repo: Repository in format "owner/repo"
            filters: Query filters

        Returns:
            List of issue dicts
        """
        # Build gh command (READ-ONLY operation)
        cmd = ["gh", "issue", "list", "--json",
               "number,title,state,author,labels,assignees,createdAt,updatedAt,closedAt,url,body",
               "--limit", "100"]

        # Add repo
        cmd.extend(["--repo", repo])

        # Apply filters
        if filters:
            if 'state' in filters:
                state = filters['state'].lower()
                if state in ['open', 'closed', 'all']:
                    cmd.extend(["--state", state])

            if 'label' in filters:
                cmd.extend(["--label", filters['label']])

            if 'assignee' in filters:
                cmd.extend(["--assignee", filters['assignee']])

            if 'author' in filters:
                cmd.extend(["--author", filters['author']])

            if 'mention' in filters:
                cmd.extend(["--mention", filters['mention']])

        # Check if we want PRs specifically
        if filters and filters.get('type') == 'pr':
            cmd[1] = "pr"  # Change 'issue' to 'pr'

        try:
            # Execute READ-ONLY gh command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            issues = json.loads(result.stdout)

            # Add repo information to each issue for multi-repo queries
            for issue in issues:
                issue['repo'] = repo

            # Apply additional filters that gh doesn't support directly
            if filters:
                # Filter by date range
                if 'created_after' in filters:
                    date_value = self._parse_date_filter(filters['created_after'])
                    issues = [
                        issue for issue in issues
                        if datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00')) >= date_value
                    ]

                if 'updated_after' in filters:
                    date_value = self._parse_date_filter(filters['updated_after'])
                    issues = [
                        issue for issue in issues
                        if datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00')) >= date_value
                    ]

                # Search in title/body
                if 'search' in filters:
                    search_term = filters['search'].lower()
                    issues = [
                        issue for issue in issues
                        if search_term in issue.get('title', '').lower() or
                           search_term in issue.get('body', '').lower()
                    ]

            return issues

        except subprocess.CalledProcessError as e:
            # If gh command fails, return empty list
            return []
        except subprocess.TimeoutExpired:
            return []
        except json.JSONDecodeError:
            return []

    def _parse_date_filter(self, date_value: str) -> datetime:
        """
        Parse date filter value into datetime.

        Handles:
        - SQL interval expressions: "NOW() - INTERVAL '30 days'"
        - ISO dates: "2026-03-10"
        - Relative phrases: "30 days ago", "yesterday"
        """
        date_str = str(date_value).strip().upper()

        # Handle SQL interval expressions
        if "NOW()" in date_str and "INTERVAL" in date_str:
            import re
            match = re.search(r"(\d+)\s*(DAY|HOUR|WEEK|MONTH)", date_str)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == "DAY":
                    return datetime.now() - timedelta(days=amount)
                elif unit == "HOUR":
                    return datetime.now() - timedelta(hours=amount)
                elif unit == "WEEK":
                    return datetime.now() - timedelta(weeks=amount)
                elif unit == "MONTH":
                    return datetime.now() - timedelta(days=amount * 30)

        # Handle ISO dates
        try:
            return datetime.fromisoformat(date_value)
        except (ValueError, TypeError):
            pass

        # Default to now if can't parse
        return datetime.now()

    def get_attributes(self) -> List[str]:
        """Available attributes for GitHub issues"""
        return [
            'number',
            'title',
            'state',
            'author',
            'labels',
            'assignees',
            'createdAt',
            'updatedAt',
            'closedAt',
            'url',
            'body',
            'repo'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.

        Also validates that any repo filter is for Synthego organization.
        """
        valid_filters = {
            'state',
            'label',
            'assignee',
            'author',
            'mention',
            'type',
            'created_after',
            'updated_after',
            'search',
            'repo'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        # If repo is specified, validate it's Synthego
        if 'repo' in filters:
            repo_value = filters['repo']

            # "default" keyword is always valid
            if repo_value == "default":
                return True

            # Handle comma-separated list
            if ',' in repo_value:
                repos = [r.strip() for r in repo_value.split(',')]
                return all(self._validate_repo(r) for r in repos)

            # Single repo
            return self._validate_repo(repo_value)

        return True
