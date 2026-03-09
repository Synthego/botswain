"""AWS Bedrock LLM provider implementation using anthropic[bedrock] SDK"""
import json
import re
from typing import Dict, Any
from anthropic import AnthropicBedrock
from .provider import LLMProvider


class BedrockProvider(LLMProvider):
    """AWS Bedrock implementation using Anthropic SDK with inference profile"""

    def __init__(self):
        """Initialize Bedrock provider with Anthropic SDK"""
        self.client = AnthropicBedrock()
        # Use inference profile ID (not direct model ID)
        self.model_id = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'

        # Token limits per task
        self.intent_max_tokens = 500
        self.response_max_tokens = 1000

    def parse_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse natural language question into structured intent JSON using Bedrock.

        Args:
            question: User's natural language question
            context: Additional context (entity catalog, user info, etc.)

        Returns:
            Structured intent dict with entity, filters, attributes, and token usage
        """
        prompt = self._build_intent_prompt(question, context)

        response = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.intent_max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response content
        response_text = response.content[0].text

        # Parse JSON from response
        try:
            # Strip markdown code blocks if present
            cleaned_output = self._strip_markdown_json(response_text)
            intent_data = json.loads(cleaned_output)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from Bedrock: {response_text}")

        # Add token usage information
        intent_data["input_tokens"] = response.usage.input_tokens
        intent_data["output_tokens"] = response.usage.output_tokens
        intent_data["total_tokens"] = response.usage.input_tokens + response.usage.output_tokens

        return intent_data

    def format_response(self, query_results: Any, original_question: str) -> str:
        """
        Format query results into natural language response using Bedrock.

        Args:
            query_results: Query execution results
            original_question: User's original question

        Returns:
            Natural language response string (markdown formatted)
        """
        prompt = self._build_response_prompt(query_results, original_question)

        response = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.response_max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response content
        return response.content[0].text.strip()

    def _build_intent_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """Build prompt for intent parsing"""
        entities_desc = "\n".join([
            f"- {name}: {desc}"
            for name, desc in context.get('entities', {}).items()
        ])

        return f"""You are a factory query assistant. Parse this question into structured JSON.

Available entities:
{entities_desc}

Question: {question}

Return ONLY valid JSON with this structure:
{{
  "entity": "entity_name",
  "intent_type": "query|count|aggregate",
  "attributes": ["attr1", "attr2"],
  "filters": {{"key": "value"}},
  "sort": {{"field": "name", "direction": "asc"}},
  "limit": 10
}}
"""

    def _build_response_prompt(self, query_results: Any, original_question: str) -> str:
        """Build prompt for response formatting"""
        results_json = json.dumps(query_results, indent=2, default=str)

        return f"""You are a factory query assistant. Format these query results as a natural language response.

Original question: {original_question}

Query results:
{results_json}

Provide a concise, helpful natural language response in markdown format."""

    def _strip_markdown_json(self, text: str) -> str:
        """Strip markdown code blocks from JSON response"""
        # Remove ```json and ``` markers
        text = text.strip()

        # Pattern to match markdown code blocks
        pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip()

        return text
