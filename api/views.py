import copy
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny  # Change to IsAuthenticated in production
from core.llm.factory import LLMProviderFactory
from core.semantic_layer.registry import EntityRegistry
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

            # Auto-detect whether to use BARB or mock entities
            db_name = str(settings.DATABASES['default']['NAME'])
            if 'barb' in db_name:
                # Using real BARB database
                from core.semantic_layer.entities.synthesizer_barb import SynthesizerEntity
                from core.semantic_layer.entities.instrument_barb import InstrumentEntity

                registry.register(SynthesizerEntity())
                registry.register(InstrumentEntity())
            else:
                # Using mock/test database
                from core.semantic_layer.entities.synthesizer import SynthesizerEntity

                registry.register(SynthesizerEntity())

            # Parse intent
            llm_provider = LLMProviderFactory.get_default()
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

            # Extract text and tokens from formatted response
            if isinstance(formatted_response, dict):
                response_text = formatted_response.get('text', formatted_response)
                format_tokens = formatted_response.get('tokens', {})
            else:
                # Backwards compatibility for providers that return strings
                response_text = formatted_response
                format_tokens = {}

            # Combine tokens from parse_intent and format_response
            intent_tokens = intent.get('_tokens', {})
            combined_tokens = {
                'input': intent_tokens.get('input', 0) + format_tokens.get('input', 0),
                'output': intent_tokens.get('output', 0) + format_tokens.get('output', 0),
                'total': intent_tokens.get('total', 0) + format_tokens.get('total', 0)
            }

            # Add combined tokens back to intent for audit logging
            intent['_tokens'] = combined_tokens

            response_data = {
                'question': question,
                'response': response_text,
                'intent': intent,
                'results': query_results,
                'cached': False,
                'format_tokens': format_tokens  # Include format_response tokens separately
            }

            # Audit log (pass a copy of intent since logger.log() modifies it with pop())
            logger = AuditLogger()
            logger.log(
                user=request.user.username if request.user.is_authenticated else 'anonymous',
                intent=copy.deepcopy(intent),
                response=response_data,
                execution_time=query_results['execution_time_ms'] / 1000,
                question=question,
                interface='api',
                model=llm_provider.model
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
