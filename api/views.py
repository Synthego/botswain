import copy
from django.conf import settings
from django.core.exceptions import FieldError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny  # Change to IsAuthenticated in production
from core.llm.factory import LLMProviderFactory
from core.semantic_layer.registry import EntityRegistry
from core.query_executor import QueryExecutor
from core.audit import AuditLogger
from core.query_recovery import QueryRecovery
from core.query_planner import QueryPlanner
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
        override_limit = serializer.validated_data.get('override_limit')

        # Try executing the query, with automatic recovery on certain errors
        result = self._execute_query_with_recovery(
            question=question,
            override_limit=override_limit,
            user=request.user.username if request.user.is_authenticated else 'anonymous'
        )

        return result

    def _execute_query_with_recovery(self, question: str, override_limit: int, user: str):
        """
        Execute query with automatic error recovery.

        If query fails with a recoverable error, simplify the question and retry.
        """
        try:
            return self._execute_query(question, override_limit, user, is_retry=False)

        except (ValueError, FieldError, Exception) as e:
            error_message = str(e)

            # Check if error is recoverable
            should_retry, simplified_question = QueryRecovery.should_retry(
                question, error_message
            )

            if should_retry and simplified_question:
                # Retry with simplified question
                try:
                    result = self._execute_query(
                        simplified_question,
                        override_limit,
                        user,
                        is_retry=True,
                        original_question=question
                    )
                    return result

                except Exception as retry_error:
                    # If retry also fails, return original error
                    return Response(
                        {
                            'error': error_message,
                            'type': 'validation_error' if isinstance(e, (ValueError, FieldError)) else 'internal_error',
                            'attempted_recovery': True,
                            'simplified_question': simplified_question,
                            'recovery_error': str(retry_error)
                        },
                        status=status.HTTP_400_BAD_REQUEST if isinstance(e, (ValueError, FieldError)) else status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # Error not recoverable, return original error
                return Response(
                    {
                        'error': error_message,
                        'type': 'validation_error' if isinstance(e, (ValueError, FieldError)) else 'internal_error'
                    },
                    status=status.HTTP_400_BAD_REQUEST if isinstance(e, (ValueError, FieldError)) else status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    def _execute_query(self, question: str, override_limit: int, user: str, is_retry: bool = False, original_question: str = None):
        """Execute a single query attempt"""
        # Initialize components
        registry = EntityRegistry()

        # Check if we have BARB database configured
        has_barb = 'barb' in settings.DATABASES
        if has_barb:
            # Using real BARB database
            from core.semantic_layer.entities.synthesizer import SynthesizerEntity
            from core.semantic_layer.entities.instrument_barb import InstrumentEntity
            from core.semantic_layer.entities.workflow_barb import WorkflowEntity

            registry.register(SynthesizerEntity())
            registry.register(InstrumentEntity())
            registry.register(WorkflowEntity())
        else:
            # Using mock/test database
            from core.semantic_layer.entities.synthesizer import SynthesizerEntity

            registry.register(SynthesizerEntity())


        # Check if we have Buckaneer database configured
        has_buckaneer = 'buckaneer' in settings.DATABASES
        if has_buckaneer:
            from core.semantic_layer.entities.order_buckaneer import OrderEntity
            from core.semantic_layer.entities.netsuite_orders import NetSuiteOrderEntity

            registry.register(OrderEntity())
            registry.register(NetSuiteOrderEntity())

        # Check if we have Kraken database configured
        has_kraken = 'kraken' in settings.DATABASES
        if has_kraken:
            from core.semantic_layer.entities.kraken_workflows import KrakenWorkflowEntity

            registry.register(KrakenWorkflowEntity())

        # Check if we have SOS database configured
        has_sos = 'sos' in settings.DATABASES
        if has_sos:
            from core.semantic_layer.entities.sos_sequencing import SOSSequencingEntity

            registry.register(SOSSequencingEntity())

        # Check if GitHub CLI is available
        import shutil
        has_github = shutil.which('gh') is not None
        if has_github:
            from core.semantic_layer.entities.github_issues import GitHubIssuesEntity

            registry.register(GitHubIssuesEntity())
        
        # Check if git is available
        has_git = shutil.which('git') is not None
        if has_git:
            from core.semantic_layer.entities.git_commits import GitCommitsEntity

            registry.register(GitCommitsEntity())
        
        # Check if elasticsearch package is available
        try:
            import elasticsearch
            from core.semantic_layer.entities.instrument_logs import InstrumentLogsEntity
            registry.register(InstrumentLogsEntity())
        except ImportError:
            pass  # elasticsearch package not installed

        # Check if boto3 is available for CloudWatch Logs
        try:
            import boto3
            from core.semantic_layer.entities.service_logs import ServiceLogsEntity
            registry.register(ServiceLogsEntity())
        except ImportError:
            pass  # boto3 package not installed

        # Check if boto3 is available for ECS cluster status
        try:
            import boto3
            from core.semantic_layer.entities.ecs_services import ECSServicesEntity
            registry.register(ECSServicesEntity())
        except ImportError:
            pass  # boto3 package not installed

        # Check if boto3 is available for RDS database status
        try:
            import boto3
            from core.semantic_layer.entities.rds_databases import RDSDatabaseEntity
            registry.register(RDSDatabaseEntity())
        except ImportError:
            pass  # boto3 package not installed

        # Initialize LLM provider

        # Initialize LLM provider
        llm_provider = LLMProviderFactory.get_default()

        # Check if this is a multi-entity query using QueryPlanner
        planner = QueryPlanner(llm_provider)
        is_multi, multi_result = planner.execute_multi_entity_query(
            question,
            registry.get_entity_descriptions(),
            QueryExecutor(registry=registry),
            user
        )

        if is_multi:
            # Multi-entity query was executed, return synthesized response
            response_data = {
                'question': original_question if is_retry else question,
                'response': multi_result['synthesized_response'],
                'multi_entity': True,
                'entities': multi_result['analysis']['entities_needed'],
                'sub_queries': [
                    {
                        'entity': sq['entity'],
                        'question': sq['question'],
                        'result_count': sq['result'].get('count', 0) if sq['result'] else 0,
                        'execution_time_ms': sq['result'].get('execution_time_ms', 0) if sq['result'] else 0
                    }
                    for sq in multi_result['sub_queries']
                ],
                'total_execution_time_ms': multi_result['total_execution_time_ms'],
                'cached': False
            }

            # Audit log for multi-entity query
            logger = AuditLogger()
            logger.log(
                user=user,
                intent={'entity': 'multi', 'entities': multi_result['analysis']['entities_needed']},
                response=response_data,
                execution_time=multi_result['total_execution_time_ms'] / 1000,
                question=original_question if is_retry else question,
                interface='api',
                model=llm_provider.model
            )

            return Response(response_data)

        # Single-entity query - proceed with normal flow
        intent = llm_provider.parse_intent(question, {
            'entities': registry.get_entity_descriptions()
        })

        # Apply limit override if provided
        if override_limit is not None:
            intent['limit'] = override_limit

        # Execute query
        executor = QueryExecutor(registry=registry)
        query_results = executor.execute(intent, user=user)

        # Format response (pass intent for limit transparency)
        formatted_response = llm_provider.format_response(
            query_results,
            original_question if is_retry else question,  # Use original question for context
            intent
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
            'question': original_question if is_retry else question,
            'response': response_text,
            'intent': intent,
            'results': query_results,
            'cached': False,
            'format_tokens': format_tokens
        }

        # Add recovery metadata if this was a retry
        if is_retry:
            response_data['recovered'] = True
            response_data['simplified_question'] = question

        # Audit log (pass a copy of intent since logger.log() modifies it with pop())
        logger = AuditLogger()
        logger.log(
            user=user,
            intent=copy.deepcopy(intent),
            response=response_data,
            execution_time=query_results['execution_time_ms'] / 1000,
            question=original_question if is_retry else question,
            interface='api',
            model=llm_provider.model
        )

        return Response(response_data)

