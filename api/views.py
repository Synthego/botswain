from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny  # Change to IsAuthenticated in production
from core.llm.factory import LLMProviderFactory
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.synthesizer import SynthesizerEntity
from core.query_executor import QueryExecutor
from core.audit import AuditLogger
from .serializers import QueryRequestSerializer

class QueryAPIView(APIView):
    """POST /api/query - Main endpoint for natural language queries"""

    permission_classes = [AllowAny]  # TODO: Change to IsAuthenticated

    def post(self, request):
        serializer = QueryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        question = serializer.validated_data['question']
        format_type = serializer.validated_data.get('format', 'natural')

        try:
            # Initialize components
            registry = EntityRegistry()
            registry.register(SynthesizerEntity())

            # Parse intent (mock for now)
            llm_provider = LLMProviderFactory.create('claude_cli')
            intent = llm_provider.parse_intent(question, {
                'entities': registry.get_entity_descriptions()
            })

            # Execute query
            executor = QueryExecutor(registry=registry)
            query_results = executor.execute(
                intent,
                user=request.user.username if request.user.is_authenticated else 'anonymous'
            )

            # Format response
            formatted_response = llm_provider.format_response(
                query_results,
                question
            )

            response_data = {
                'question': question,
                'response': formatted_response,
                'intent': intent,
                'results': query_results,
                'cached': False
            }

            # Audit log
            logger = AuditLogger()
            logger.log(
                user=request.user.username if request.user.is_authenticated else 'anonymous',
                intent=intent,
                response=response_data,
                execution_time=query_results['execution_time_ms'] / 1000,
                question=question,
                interface='api'
            )

            return Response(response_data)

        except ValueError as e:
            return Response(
                {'error': str(e), 'type': 'validation_error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e), 'type': 'internal_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
