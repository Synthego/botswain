from rest_framework import serializers

class QueryRequestSerializer(serializers.Serializer):
    """Serializer for query request"""

    question = serializers.CharField(
        required=True,
        max_length=1000,
        help_text="Natural language question"
    )

    format = serializers.ChoiceField(
        choices=['natural', 'json', 'table'],
        default='natural',
        required=False,
        help_text="Response format"
    )

    use_cache = serializers.BooleanField(
        default=True,
        required=False,
        help_text="Whether to use cached results"
    )

class QueryResponseSerializer(serializers.Serializer):
    """Serializer for query response"""

    success = serializers.BooleanField()
    question = serializers.CharField()
    response = serializers.CharField()
    intent = serializers.JSONField(required=False)
    results = serializers.JSONField(required=False)
    execution_time_ms = serializers.IntegerField(required=False)
    cache_hit = serializers.BooleanField(required=False, default=False)
    error = serializers.CharField(required=False, allow_null=True)
