"""AWS Bedrock LLM provider implementation using anthropic[bedrock] SDK"""
import json
import re
from typing import Dict, Any, Optional
from anthropic import AnthropicBedrock
from django.conf import settings
from .provider import LLMProvider


class BedrockProvider(LLMProvider):
    """AWS Bedrock implementation using Anthropic SDK with inference profile"""

    def __init__(
        self,
        model: Optional[str] = None,
        max_intent_tokens: Optional[int] = None,
        max_response_tokens: Optional[int] = None,
        timeout: Optional[float] = None
    ):
        """
        Initialize Bedrock provider with Anthropic SDK.

        Args:
            model: Bedrock model inference profile ID (defaults to settings.BEDROCK_MODEL_ID)
            max_intent_tokens: Max tokens for intent parsing (defaults to settings.BEDROCK_MAX_INTENT_TOKENS)
            max_response_tokens: Max tokens for response formatting (defaults to settings.BEDROCK_MAX_RESPONSE_TOKENS)
            timeout: Request timeout in seconds (defaults to settings.BEDROCK_TIMEOUT)
        """
        # Use settings as defaults if not provided
        self.model = model or settings.BEDROCK_MODEL_ID
        self.max_intent_tokens = max_intent_tokens or settings.BEDROCK_MAX_INTENT_TOKENS
        self.max_response_tokens = max_response_tokens or settings.BEDROCK_MAX_RESPONSE_TOKENS
        timeout_value = timeout or settings.BEDROCK_TIMEOUT

        self.client = AnthropicBedrock(
            timeout=timeout_value,
            max_retries=2
        )

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
            model=self.model,
            max_tokens=self.max_intent_tokens,
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

        # Add token usage information in nested structure
        intent_data["_tokens"] = {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
            "total": response.usage.input_tokens + response.usage.output_tokens
        }

        return intent_data

    def format_response(self, query_results: Any, original_question: str, intent: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format query results into natural language response using Bedrock.

        Args:
            query_results: Query execution results
            original_question: User's original question
            intent: Optional parsed intent (unused - kept for API compatibility)

        Returns:
            Dict with 'text' (formatted response) and 'tokens' (usage info)
        """
        prompt = self._build_response_prompt(query_results, original_question)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_response_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        # Return both the formatted text and token usage
        return {
            'text': response.content[0].text.strip(),
            'tokens': {
                'input': response.usage.input_tokens,
                'output': response.usage.output_tokens,
                'total': response.usage.input_tokens + response.usage.output_tokens
            }
        }

    def _build_intent_prompt(self, question: str, context: Dict[str, Any]) -> str:
        """Build prompt for intent parsing"""
        entities_desc = "\n".join([
            f"- {name}: {desc}"
            for name, desc in context.get('entities', {}).items()
        ])

        return f"""You are a factory query assistant. Parse this question into structured JSON.

Available entities:
{entities_desc}

VALID FILTERS BY ENTITY (use ONLY these - do NOT invent others):
- synthesizer: status, available, barcode
- instrument: status, factory, barcode, instrument_type, type
- workflow: status, template, template_name, work_order_id, workflow_id, created_after, created_before
- order: status, factory, bigcommerce_id, order_id, created_after, created_before, email
- github_issue: state, label, assignee, author, mention, type, created_after, updated_after, search, repo
- git_commit: author, since, until, search, message, branch, repo, limit
- instrument_log: instrument_type, module_name, synthesizer, instrument, level, tags, synthesis_id, workorder_id, work_order_id, plate_barcode, barcode, search, message, since, start_time, until, end_time, limit, sort_order
- service_log: service, environment, level, role, search, message, since, start_time, until, end_time, limit
- ecs_service: service, environment, role, status, cluster
- rds_database: database, service, environment, status, replica, include_metrics
- netsuite_order: order_id, external_id, internal_id, netsuite_id, status, customer, customer_name, since, start_date, until, end_date, limit

Filter mapping rules (CRITICAL - follow these exactly):

1. Status values:
   - Use "online" for: working, operational, available, up, running
   - Use "offline" for: down, broken, not working, unavailable, failed

2. Date ranges (for workflow entity):
   - "last 30 days" → created_after: "NOW() - INTERVAL '30 days'"
   - "yesterday" → created_after: "NOW() - INTERVAL '1 day'"
   - "this week" → created_after: "NOW() - INTERVAL '7 days'"
   - "this month" → created_after: "NOW() - INTERVAL '30 days'"
   - Use ISO format for specific dates: "2026-03-10"

3. Template names (for workflow entity):
   - Use filter "template" or "template_name" with partial match
   - Examples: "RNA synthesis" → template: "RNA", "Plating" → template: "Plating"

4. Work orders (for workflow entity):
   - Use filter "work_order_id" with numeric ID
   - Example: "work order 578630" → work_order_id: 578630

5. Barcodes (for synthesizer/instrument entities):
   - Use filter "barcode" with exact value
   - Example: "synthesizer 1717" → barcode: 1717

6. GitHub issues (for github_issue entity):
   - SECURITY: Only Synthego organization repos allowed (e.g., "Synthego/barb")
   - State: "open", "closed", or "all"
   - Type: "pr" for pull requests only
   - Repo: Can be single repo "Synthego/barb" or comma-separated list "Synthego/barb,Synthego/buckaneer"
   - Repo inference rules:
     * If question mentions specific project (barb, buckaneer, kraken, etc.) → use that repo
     * If question is general ("my issues", "assigned to X") → use "default" to search key repos
     * Available repos: barb, buckaneer, kraken, galleon, catamaran, hook, line, sos, mazu, crab
   - Examples:
     - "open issues" → state: "open", repo: "default"
     - "my open issues" → state: "open", assignee: "danajanezic", repo: "default"
     - "closed PRs in barb repo" → state: "closed", type: "pr", repo: "Synthego/barb"
     - "issues assigned to bob" → assignee: "bob", repo: "default"
     - "issues with bug label" → label: "bug", repo: "default"
     - "barb issues about midscale" → search: "midscale", repo: "Synthego/barb"
   - IMPORTANT: Non-Synthego repos will be rejected

7. Git commits (for git_commit entity):
   - Searches git commit history across local repository clones
   - Author: commit author name (e.g., "Dana Janezic", "danajanezic")
   - Date filters: since, until (accepts same formats as workflow dates)
   - Message search: search or message filter (searches commit subject and body)
   - Branch: specific branch name (default: searches all branches)
   - Repo: Can be single repo "barb" or comma-separated list "barb,buckaneer"
   - Repo inference rules (same as github_issue):
     * If question mentions specific project → use that repo
     * If question is general ("my commits", "recent changes") → use "default" to search key repos
     * Available repos: barb, buckaneer, kraken, galleon, hook, line, sos
   - Examples:
     - "my recent commits" → author: "danajanezic", repo: "default"
     - "commits in barb repo last week" → repo: "barb", since: "NOW() - INTERVAL '7 days'"
     - "commits about midscale" → search: "midscale", repo: "default"
     - "commits by dana in last 30 days" → author: "dana", since: "NOW() - INTERVAL '30 days'", repo: "default"

8. Instrument logs (for instrument_log entity):
   - Searches ALL Synthego-Brain instrument logs from ElasticSearch cluster
   - Covers SSA synthesizers, Hamilton instruments, Tecan instruments, and all other lab modules
   - IMPORTANT: Requires VPN connection for production ElasticSearch access
   - Instrument types:
     * "ssa" or "synthesizer" → SolidStateSynthesizerModule (RNA synthesis runs)
     * "hamilton" → HamiltonInstrument (liquid handling, plate preparation)
     * "tecan" → TecanInstrument (plate handling, processing)
   - Date filters: since/start_time, until/end_time (accepts same formats as workflow dates)
   - Message search: search or message filter (searches log message text)
   - Level: ERROR, INFO, WARNING, DEBUG (case-insensitive)
   - Tags: Log tags for filtering specific events
   - Work order tracking: synthesis_id, workorder_id, work_order_id
   - Plate tracking (Hamilton/Tecan): plate_barcode, barcode, linked_barcodes
   - Examples:
     - "SSA errors today" → instrument_type: "ssa", level: "ERROR", since: "now-24h"
     - "Hamilton logs for plate ABC123" → instrument_type: "hamilton", plate_barcode: "ABC123"
     - "synthesis logs for work order 578630" → workorder_id: 578630
     - "all instrument errors this week" → level: "ERROR", since: "NOW() - INTERVAL '7 days'"
     - "Tecan operations today" → instrument_type: "tecan", since: "now-24h"

9. Service logs (for service_log entity):
   - Searches Django/FastAPI/gRPC service logs from AWS CloudWatch Logs
   - Covers BARB, Buckaneer, Kraken, SOS, Hook, Line, and other web services
   - IMPORTANT: Requires AWS credentials (IAM or SSO)
   - RETENTION: Production 30 days, Stage 14 days, QA/Dev 7 days (queries outside retention window return no results)
   - Services:
     * "barb" or "barb-prod" → BARB production Django web server and Celery workers
     * "buckaneer" or "buckaneer-prod" → Buckaneer e-commerce backend
     * "kraken" or "kraken-prod" → Kraken workflow orchestration
     * "sos" or "sos-prod" → SOS sequencing coordination
     * Can specify environment: "barb-stage", "buckaneer-qa", etc.
   - Level: ERROR, WARNING, INFO, DEBUG (case-insensitive)
   - Role: web (Django/FastAPI server), worker (Celery worker), beat (Celery scheduler)
   - Date filters: since/start_time, until/end_time (accepts same formats as workflow dates)
   - Message search: search or message filter (searches log message text)
   - Examples:
     - "BARB errors today" → service: "barb", level: "ERROR", since: "24h"
     - "Buckaneer 500 errors in the last hour" → service: "buckaneer", search: "500", since: "1h"
     - "Celery task failures in BARB this week" → service: "barb", role: "worker", search: "Task.*failed", since: "7d"
     - "Kraken errors in stage environment" → service: "kraken", environment: "stage", level: "ERROR", since: "24h"
     - "Django exceptions in any service today" → search: "Traceback", since: "24h"

10. ECS service status (for ecs_service entity):
   - Queries AWS ECS cluster for service operational status and health
   - Covers BARB, Buckaneer, Kraken, SOS, Hook, Line services
   - IMPORTANT: Requires AWS credentials (IAM or SSO)
   - Services:
     * "barb" → Returns all BARB services (web, worker, beat)
     * "buckaneer" → Returns all Buckaneer services (web, worker)
     * "kraken", "sos", "hook", "line" → Individual services
   - Environment: prod (default), stage, qa, all
   - Role: web (Django/FastAPI server), worker (Celery worker), beat (Celery scheduler)
   - Status: running (services with running tasks), stopped (services with no running tasks)
   - Returns: service name, task counts (desired vs running), health status, deployment status
   - Examples:
     - "Is BARB running?" → service: "barb", environment: "prod"
     - "Show me all production services" → environment: "prod"
     - "How many Buckaneer tasks are running?" → service: "buckaneer"
     - "What's the status of BARB workers?" → service: "barb", role: "worker"
     - "Are there any stopped services?" → status: "stopped"
     - "Show me stage environment services" → environment: "stage"

11. RDS database status (for rds_database entity):
   - Queries AWS RDS database operational status and configuration
   - Covers BARB, Buckaneer, Kraken, SOS PostgreSQL databases
   - IMPORTANT: Requires AWS credentials (IAM or SSO)
   - Database naming pattern: <service>-<environment>-pg-<number>
   - Services:
     * "barb" → barb-prod-pg-0 (primary), barb-prod-pg-replica-0 (read replica)
     * "buckaneer" → buckaneer-prod-pg-0
     * "kraken", "sos" → Individual production databases
   - Environment: prod (default), stage, qa, dev, all
   - Status: available, backing-up, modifying, etc. (RDS instance status)
   - Replica: true (only read replicas), false (only primary instances)
   - Returns: database status, instance type, storage, Multi-AZ, engine version, connections, CPU, endpoints
   - Examples:
     - "Is the BARB database available?" → service: "barb", environment: "prod"
     - "Show me all production databases" → environment: "prod"
     - "What's the status of Buckaneer database?" → service: "buckaneer"
     - "Show me BARB read replicas" → service: "barb", replica: true
     - "How much storage does BARB database have?" → service: "barb", environment: "prod"
     - "Show me all databases in stage environment" → environment: "stage"

Question: {question}

12. NetSuite orders (for netsuite_order entity):
   - Queries NetSuite sales orders cached in Buckaneer database
   - Shows order sync status between Buckaneer and NetSuite
   - IMPORTANT: Queries cached data (not real-time NetSuite API)
   - Order Status values:
     * "pending" → Pending Fulfillment (order placed, not shipped)
     * "fulfilled" → Pending Billing (shipped, not invoiced)
     * "billed" → Partially Billed
     * "closed" → Closed (fully invoiced)
   - Filters:
     * order_id or external_id: Buckaneer order ID
     * internal_id or netsuite_id: NetSuite internal ID
     * status: pending, fulfilled, billed, closed
     * customer or customer_name: Search by customer name
   - Date filters: since, until (order creation date)
   - Returns: order totals, customer info, fulfillment status, invoice status, NetSuite IDs
   - Examples:
     - "Show me recent NetSuite orders" → (default: last 30 days)
     - "What's the NetSuite status of order 12345?" → order_id: 12345
     - "Show me unfulfilled NetSuite orders" → status: "pending"
     - "Show me orders invoiced in the last week" → status: "closed", since: "NOW() - INTERVAL '7 days'"
     - "Show me NetSuite orders for customer ABC Corp" → customer: "ABC Corp"

Return ONLY valid JSON with this structure:

Intent Types - CRITICAL FOR ACCURATE RESULTS:

1. "query" - Use for questions asking to "show", "list", "find" specific records
   - Returns raw data records
   - Example: "Show me available synthesizers"

2. "count" - Use for questions asking "how many", "count", "number of"
   - Returns accurate programmatic count
   - Supports GROUP BY for grouped counts
   - Example: "How many orders were placed this week?"
   - With grouping: "Count orders by status"
   - Add "group_by": "field_name" for grouped counts

3. "aggregate" - Use for questions about totals, averages, min/max
   - Returns programmatic calculations (SUM, AVG, MIN, MAX)
   - Example: "What's the total revenue this month?"
   - Example: "What's the average order value?"
   - Add "aggregation_function": "sum|avg|min|max" (optional, defaults to all)

{{
  "entity": "entity_name",
  "intent_type": "query|count|aggregate",
  "attributes": ["attr1", "attr2"],
  "filters": {{"key": "value"}},
  "sort": {{"field": "name", "direction": "asc"}},
  "limit": 10,
  "aggregation_function": "sum|avg|min|max",  // Optional: for aggregate intent_type
  "group_by": "field_name"  // Optional: for count intent_type
}}

CRITICAL: Only use filters listed above for the chosen entity. If question asks about something not in valid filters, return empty filters object.
"""

    def _build_response_prompt(self, query_results: Any, original_question: str) -> str:
        """Build prompt for response formatting"""
        results_json = json.dumps(query_results, indent=2, default=str)

        # Don't include the original question verbatim to avoid Bedrock refusal triggers
        return f"""Database query results:

{results_json}

Write a natural language summary of these results in markdown format."""


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
