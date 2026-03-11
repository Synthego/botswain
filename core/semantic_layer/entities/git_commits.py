"""
Git Commits entity for querying commit history.
Uses git log command for READ-ONLY access.

SECURITY: Read-only git operations only. Restricted to Synthego repositories.
"""
import json
import subprocess
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseEntity


class GitCommitsEntity(BaseEntity):
    """
    Queries git commit history using git log command.

    SECURITY RESTRICTIONS:
    - READ-ONLY access via git log
    - Only searches local repository clones
    - No write operations allowed
    """

    name = "git_commit"
    description = "Git commit history from Synthego repositories. Use for questions about code changes, who made changes, when changes were made, commit messages."

    # Default repos to search when no specific repo is mentioned
    DEFAULT_REPOS = [
        "barb",
        "buckaneer",
        "kraken",
        "galleon",
        "hook",
        "line",
        "sos",
    ]

    # Base path where repos are cloned
    REPO_BASE_PATH = "/home/danajanezic/code"

    def _get_repo_path(self, repo_name: str) -> str:
        """
        Get file system path for a repository.

        Args:
            repo_name: Repository name (e.g., "barb", "buckaneer")

        Returns:
            Full path to repository
        """
        return f"{self.REPO_BASE_PATH}/{repo_name}"

    def get_queryset(self, filters: Dict[str, Any] = None):
        """
        Get commits from git log (READ-ONLY).

        Returns a list of dicts (not a Django queryset) since git is a file system operation.

        SECURITY: All operations are read-only. No modifications to git history.
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
            # Default to searching all key repos
            repos = self.DEFAULT_REPOS

        # Query each repo and combine results
        all_commits = []
        for repo in repos:
            commits = self._query_single_repo(repo, filters)
            all_commits.extend(commits)

        # Sort combined results by date (most recent first)
        all_commits.sort(key=lambda c: c.get('date', ''), reverse=True)

        return all_commits

    def _query_single_repo(self, repo_name: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query a single repository for commits.

        Args:
            repo_name: Repository name (e.g., "barb")
            filters: Query filters

        Returns:
            List of commit dicts
        """
        repo_path = self._get_repo_path(repo_name)

        # Build git log command (READ-ONLY operation)
        # Format: hash|author|date|subject|body
        cmd = [
            "git", "log",
            "--format=%H|%an|%ae|%ai|%s|%b",
            "--all",  # Search all branches
            "-n", "100"  # Limit to 100 commits per repo
        ]

        # Apply filters
        if filters:
            # Author filter
            if 'author' in filters:
                cmd.extend(["--author", filters['author']])

            # Date range filters
            if 'since' in filters:
                date_value = self._parse_date_filter(filters['since'])
                cmd.extend(["--since", date_value.isoformat()])

            if 'until' in filters:
                date_value = self._parse_date_filter(filters['until'])
                cmd.extend(["--until", date_value.isoformat()])

            # Message search filter
            if 'search' in filters or 'message' in filters:
                search_term = filters.get('search') or filters.get('message')
                cmd.extend(["--grep", search_term, "-i"])  # -i for case-insensitive

            # Branch filter
            if 'branch' in filters:
                # Remove --all and specify branch
                cmd.remove("--all")
                cmd.append(filters['branch'])

            # Limit override
            if 'limit' in filters:
                limit_idx = cmd.index("-n") + 1
                cmd[limit_idx] = str(filters['limit'])

        try:
            # Execute READ-ONLY git command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30
            )

            if result.returncode != 0:
                # Repo doesn't exist or git command failed
                return []

            # Parse git log output
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('|', 5)
                if len(parts) < 5:
                    continue

                commit_hash, author_name, author_email, date, subject = parts[:5]
                body = parts[5] if len(parts) > 5 else ""

                commits.append({
                    'hash': commit_hash,
                    'short_hash': commit_hash[:7],
                    'author_name': author_name,
                    'author_email': author_email,
                    'date': date,
                    'subject': subject,
                    'body': body.strip(),
                    'repo': repo_name
                })

            return commits

        except subprocess.TimeoutExpired:
            return []
        except Exception:
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
        """Available attributes for git commits"""
        return [
            'hash',
            'short_hash',
            'author_name',
            'author_email',
            'date',
            'subject',
            'body',
            'repo'
        ]

    def validate_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Validate that filters are safe and recognized.
        """
        valid_filters = {
            'author',
            'since',
            'until',
            'search',
            'message',
            'branch',
            'repo',
            'limit'
        }

        # Check all filter keys are valid
        if not all(key in valid_filters for key in filters.keys()):
            return False

        return True
