import subprocess
import json
import re
from typing import Dict, Any, Optional
from .provider import LLMProvider

class ClaudeCLIProvider(LLMProvider):
    """Claude CLI implementation using local claude binary"""

    def __init__(self, cli_path: str = 'claude', timeout: int = 30):
        self.cli_path = cli_path
        self.timeout = timeout

    def parse_intent(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse natural language into structured intent using Claude CLI"""
        prompt = self._build_intent_prompt(question, context)

        result = subprocess.run(
            [self.cli_path],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        try:
            # Strip markdown code blocks if present
            cleaned_output = self._strip_markdown_json(result.stdout)
            return json.loads(cleaned_output)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from Claude: {result.stdout}")

    def format_response(self, query_results: Any, original_question: str, intent: Optional[Dict[str, Any]] = None) -> str:
        """Format query results into natural language using Claude CLI

        Args:
            query_results: Query execution results
            original_question: User's original question
            intent: Optional parsed intent (not used in CLI provider)
        """
        prompt = self._build_response_prompt(query_results, original_question)

        result = subprocess.run(
            [self.cli_path],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        return result.stdout.strip()

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

Provide a concise, helpful natural language response."""

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
