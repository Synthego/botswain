from typing import Dict, Any
from django.utils import timezone
from django.contrib.auth.models import User
from .models import QueryLog

class AuditLogger:
    """Central audit logging for all queries"""

    def log(self,
            user: str,
            intent: Dict[str, Any],
            response: Dict[str, Any],
            execution_time: float,
            question: str = None,
            interface: str = 'api',
            cache_hit: bool = False) -> QueryLog:
        """
        Log a completed query.

        Args:
            user: Username or email
            intent: Structured intent dict
            response: Query execution response
            execution_time: Execution time in seconds
            question: Original question text
            interface: Where query came from (api, slack, cli)
            cache_hit: Whether result was cached

        Returns:
            Created QueryLog entry
        """
        # Extract user info
        user_obj = None
        try:
            user_obj = User.objects.get(username=user)
        except User.DoesNotExist:
            pass

        # Extract token usage if present (remove from intent_data to avoid redundancy)
        token_data = intent.pop('_tokens', {})

        # Create log entry
        log_entry = QueryLog.objects.create(
            user=user_obj,
            username=user,
            user_email=user_obj.email if user_obj else None,
            question=question or intent.get('question', ''),
            intent=intent,
            entity=intent.get('entity', ''),
            intent_type=intent.get('intent_type', ''),
            execution_time_ms=int(execution_time * 1000),
            result_count=(
                len(response.get('results', []))
                if isinstance(response.get('results'), list)
                else None
            ),
            response=response.get('response', ''),
            interface=interface,
            success=response.get('success', True),
            error_message=response.get('error'),
            cache_hit=cache_hit,
            input_tokens=token_data.get('input'),
            output_tokens=token_data.get('output'),
            total_tokens=token_data.get('total')
        )

        return log_entry

    def log_error(self,
                  user: str,
                  question: str,
                  error: Exception,
                  interface: str = 'api'):
        """Log a failed query attempt"""
        QueryLog.objects.create(
            username=user,
            question=question,
            intent={},
            entity='',
            intent_type='',
            execution_time_ms=0,
            interface=interface,
            success=False,
            error_message=str(error)
        )
