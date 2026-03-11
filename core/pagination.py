"""
Pagination metadata builder.

Calculates comprehensive pagination metadata for API responses.
"""
from typing import Dict, Any, Union


class PaginationMetadata:
    """Build pagination metadata from query results"""

    @staticmethod
    def build(offset: int, limit: int, has_next: bool, has_previous: bool,
              result_count: int) -> Dict[str, Any]:
        """
        Build comprehensive pagination metadata.

        Args:
            offset: Number of results skipped
            limit: Maximum results per page
            has_next: More results available
            has_previous: Can navigate backwards
            result_count: Number of results in current response

        Returns:
            Dictionary with pagination metadata
        """
        current_page = (offset // limit) + 1

        metadata = {
            'current_page': current_page,
            'page_size': limit,
            'offset': offset,
            'limit': limit,
            'has_next': has_next,
            'has_previous': has_previous,
        }

        # Add next/previous helpers
        if has_next:
            metadata['next_page'] = current_page + 1
            metadata['next_offset'] = offset + limit

        if has_previous:
            metadata['previous_page'] = current_page - 1
            metadata['previous_offset'] = max(0, offset - limit)

        # Estimated or exact totals
        if has_next:
            # We know there are at least offset + result_count + 1
            min_total = offset + result_count + 1
            metadata['estimated_total'] = f"{min_total}+"
            metadata['estimated_total_pages'] = f"{current_page + 1}+"
        else:
            # This is the last page, exact total known
            exact_total = offset + result_count
            metadata['estimated_total'] = exact_total
            metadata['estimated_total_pages'] = current_page if exact_total > 0 else 0

        return metadata
