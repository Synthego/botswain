"""
Query planner for handling multi-entity and cross-datasource queries.

Detects when a question requires multiple entities, breaks it into sub-queries,
and coordinates execution across data sources.
"""
import json
from typing import Dict, Any, List, Tuple, Optional
from anthropic import AnthropicBedrock
from django.conf import settings


class QueryPlanner:
    """
    Plans and coordinates multi-entity queries.

    When a question requires data from multiple entities (e.g., "show synthesizers and orders"),
    this planner breaks it into individual sub-queries, executes them, and synthesizes results.
    """

    def __init__(self, llm_provider):
        """
        Initialize query planner.

        Args:
            llm_provider: LLM provider for intent parsing and response formatting
        """
        self.llm_provider = llm_provider
        self.client = AnthropicBedrock(
            timeout=30.0,
            max_retries=2
        )

    def analyze_query_complexity(self, question: str, entity_descriptions: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze if a query requires multiple entities.

        Args:
            question: User's natural language question
            entity_descriptions: Available entities and their descriptions

        Returns:
            Dict with:
                - is_multi_entity: bool
                - entities_needed: List[str] (entity names)
                - reasoning: str (why multi-entity is needed)
                - sub_questions: List[str] (individual questions for each entity)
        """
        entities_list = "\n".join([
            f"- {name}: {desc}"
            for name, desc in entity_descriptions.items()
        ])

        prompt = f"""You are a query analyzer. Determine if this question requires data from multiple entities.

Available entities:
{entities_list}

Question: {question}

Analyze if this question can be answered with a SINGLE entity query, or if it requires MULTIPLE entities.

Examples:
- "Show offline synthesizers" → SINGLE entity (synthesizer)
- "Show recent orders" → SINGLE entity (order)
- "Show synthesizers and orders" → MULTIPLE entities (synthesizer, order)
- "How many orders were created while synthesizers were offline?" → MULTIPLE entities (needs order data + synthesizer data)
- "Show workflows from factory CR" → SINGLE entity (workflow, factory is just a filter)

Return ONLY valid JSON:
{{
  "is_multi_entity": true/false,
  "entities_needed": ["entity1", "entity2"],
  "reasoning": "brief explanation",
  "sub_questions": [
    "question for entity1",
    "question for entity2"
  ]
}}

If SINGLE entity, set is_multi_entity=false and entities_needed to single item.
"""

        response = self.client.messages.create(
            model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()

        # Strip markdown if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        try:
            analysis = json.loads(response_text)
            return analysis
        except json.JSONDecodeError as e:
            # If parsing fails, assume single entity
            return {
                "is_multi_entity": False,
                "entities_needed": [],
                "reasoning": f"Failed to parse analysis: {e}",
                "sub_questions": [question]
            }

    def synthesize_multi_entity_response(
        self,
        original_question: str,
        sub_results: List[Dict[str, Any]]
    ) -> str:
        """
        Synthesize a unified response from multiple entity queries.

        Args:
            original_question: User's original question
            sub_results: List of query results from each entity

        Returns:
            Natural language response combining all results
        """
        # Format all results for the LLM
        results_summary = []
        for i, result in enumerate(sub_results, 1):
            entity = result.get('entity', 'unknown')
            count = result.get('count', 0)
            execution_time = result.get('execution_time_ms', 0)

            results_summary.append(f"""
Query {i} - Entity: {entity}
Results: {count} records
Execution time: {execution_time}ms
Data sample: {json.dumps(result.get('results', [])[:5], indent=2, default=str)}
""")

        combined_results = "\n---\n".join(results_summary)

        prompt = f"""You are synthesizing results from multiple database queries to answer a user's question.

Original question: {original_question}

Query results from multiple data sources:
{combined_results}

Synthesize these results into a single, coherent natural language response in markdown format.

Guidelines:
- Directly answer the user's original question
- Combine insights from all queries
- Show relationships between data sources when relevant
- Use clear section headers
- Include key statistics from each source
- Keep it concise but comprehensive
"""

        response = self.client.messages.create(
            model=settings.BEDROCK_MODEL_ID,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def execute_multi_entity_query(
        self,
        question: str,
        entity_descriptions: Dict[str, str],
        query_executor,
        user: str
    ) -> Tuple[bool, Any]:
        """
        Execute a multi-entity query by breaking it into sub-queries.

        Args:
            question: User's question
            entity_descriptions: Available entities
            query_executor: QueryExecutor instance
            user: Username for audit

        Returns:
            Tuple of (is_multi_entity: bool, result: Dict or single result)

            If multi-entity, result is Dict with:
                - original_question: str
                - sub_queries: List[Dict] (each with entity, question, results)
                - synthesized_response: str
                - total_execution_time_ms: int

            If single-entity, result is the normal query result Dict
        """
        # Analyze query complexity
        analysis = self.analyze_query_complexity(question, entity_descriptions)

        # If single entity, return indication to use normal flow
        if not analysis['is_multi_entity']:
            return (False, None)

        # Execute sub-queries
        sub_results = []
        total_time = 0

        for i, (entity_name, sub_question) in enumerate(
            zip(analysis['entities_needed'], analysis['sub_questions'])
        ):
            try:
                # Parse intent for this sub-question
                intent = self.llm_provider.parse_intent(sub_question, {
                    'entities': entity_descriptions
                })

                # Execute query
                result = query_executor.execute(intent, user=user)

                sub_results.append({
                    'entity': entity_name,
                    'question': sub_question,
                    'intent': intent,
                    'result': result
                })

                total_time += result.get('execution_time_ms', 0)

            except Exception as e:
                # If sub-query fails, include error in results
                sub_results.append({
                    'entity': entity_name,
                    'question': sub_question,
                    'error': str(e),
                    'result': None
                })

        # Synthesize unified response
        synthesized = self.synthesize_multi_entity_response(
            question,
            [sr['result'] for sr in sub_results if sr['result']]
        )

        # Build combined result
        multi_result = {
            'original_question': question,
            'is_multi_entity': True,
            'analysis': analysis,
            'sub_queries': sub_results,
            'synthesized_response': synthesized,
            'total_execution_time_ms': total_time,
            'entity_count': len(analysis['entities_needed'])
        }

        return (True, multi_result)
