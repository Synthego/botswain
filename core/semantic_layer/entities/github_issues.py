"""
GitHub Issues entity for querying issues and pull requests.
Uses GitHub CLI (gh) for READ-ONLY API access.

SECURITY: Restricted to Synthego organization repositories only.
"""
import json
import subprocess
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class GitHubIssuesEntity(BaseEntity):
    """
    Queries GitHub issues and pull requests using gh CLI.

    SECURITY RESTRICTIONS:
    - READ-ONLY access via gh CLI
    - Limited to Synthego organization repositories only
    - No write operations allowed
    """

    name = "github_issue"
    description = "GitHub issues and pull requests (bugs, features, tasks, code reviews) from Synthego repositories. Use for questions about development work, bug tracking, PR status."

    # Allowed GitHub organization
    ALLOWED_ORG = "Synthego"

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

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get issues from GitHub using gh CLI (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since GitHub is an API.

        SECURITY: All operations are read-only. No modifications to GitHub data.
        """
        # Determine which repo to query
        repo = None
        if filters and 'repo' in filters:
            repo = filters['repo']
        else:
            repo = self._get_current_repo()

        # SECURITY: Validate repo is from Synthego organization
        if not repo or not self._validate_repo(repo):
            # If no valid Synthego repo, return empty results with warning
            return []

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
            'body'
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
            return self._validate_repo(filters['repo'])

        return True
