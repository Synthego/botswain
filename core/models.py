from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class QueryLog(models.Model):
    """Audit log for all queries executed through Botswain"""

    # User info
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    username = models.CharField(max_length=255)
    user_email = models.EmailField(blank=True, null=True)

    # Query details
    question = models.TextField()
    intent = models.JSONField()
    entity = models.CharField(max_length=100, db_index=True)
    intent_type = models.CharField(max_length=50, db_index=True)

    # Execution details
    executed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    execution_time_ms = models.IntegerField()
    result_count = models.IntegerField(null=True)

    # Response
    response = models.TextField(blank=True)

    # Interface used
    interface = models.CharField(max_length=50, db_index=True)

    # Success/failure
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.TextField(blank=True, null=True)

    # Caching
    cache_hit = models.BooleanField(default=False)

    # Token tracking (nullable for backwards compatibility with ClaudeCLIProvider)
    input_tokens = models.PositiveIntegerField(null=True, blank=True, help_text="Number of input tokens used")
    output_tokens = models.PositiveIntegerField(null=True, blank=True, help_text="Number of output tokens used")
    total_tokens = models.PositiveIntegerField(null=True, blank=True, help_text="Total tokens (input + output)")

    class Meta:
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['user', '-executed_at']),
            models.Index(fields=['entity', '-executed_at']),
        ]

    def clean(self):
        """Validate that total_tokens equals input_tokens + output_tokens"""
        super().clean()
        if all([self.input_tokens is not None, self.output_tokens is not None, self.total_tokens is not None]):
            expected_total = self.input_tokens + self.output_tokens
            if self.total_tokens != expected_total:
                raise ValidationError(
                    f"total_tokens ({self.total_tokens}) must equal input_tokens + output_tokens ({expected_total})"
                )

    def __str__(self):
        return f"{self.username}: {self.question[:50]}..."
