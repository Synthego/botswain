"""
Query recovery layer for handling complex or ambiguous natural language queries.

When a query fails with certain errors, this layer attempts to simplify and retry.
"""
import re
from typing import Dict, Any, Optional, Tuple
from anthropic import AnthropicBedrock
from django.conf import settings


class QueryRecovery:
    """Handles query failures by simplifying language and retrying"""

    # Mappings for complex/ambiguous phrases to canonical terms
    PHRASE_NORMALIZATIONS = {
        # Synthesis-related phrases
        r'\bsynthesis\s+(?:instruments?|machines?|equipment)\b': 'synthesizers',
        r'\bRNA\s+synthesis\s+(?:machines?|instruments?|equipment)\b': 'synthesizers',
        r'\bDNA\s+synthesis\s+(?:machines?|instruments?|equipment)\b': 'synthesizers',
        r'\bsynth\s+(?:machines?|instruments?|equipment)\b': 'synthesizers',
        r'\bsynthesis\b': 'synthesizers',  # Aggressive fallback

        # Status-related phrases - order matters! Check "not X" BEFORE "X"
        r'\bnot\s+(?:working|operational|available)\b': 'offline',
        r'\b(?:working|operational|available|up|running)\b': 'online',
        r'\b(?:down|broken|unavailable|failed)\b': 'offline',

        # Legacy explicit status patterns (backwards compatibility)
        r'\b(?:are|is)\s+down\b': 'offline',
        r'\b(?:are|is)\s+broken\b': 'offline',
        r'\b(?:are|is)\s+up\b': 'online',
        r'\b(?:are|is)\s+operational\b': 'online',
        r'\b(?:are|is)\s+available\b': 'online',

        # Workflow-related phrases
        r'\bworkflow\s+runs?\b': 'workflows',
        r'\bprocess(?:es)?\s+(?:that\s+)?ran\b': 'workflows',
        r'\bexecution[s]?\b': 'workflows',
    }

    # Common errors that indicate recoverable issues
    RECOVERABLE_ERROR_PATTERNS = [
        r"Cannot resolve keyword '(\w+)' into field",
        r"Invalid filters for entity",
        r"Unknown entity:",
        r"list index out of range",
    ]

    @classmethod
    def is_recoverable_error(cls, error_message: str) -> bool:
        """
        Check if an error is recoverable through query simplification.

        Args:
            error_message: Error message from failed query

        Returns:
            True if error can potentially be fixed by simplifying the query
        """
        if not error_message:
            return False

        for pattern in cls.RECOVERABLE_ERROR_PATTERNS:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
        return False

    @classmethod
    def simplify_question_with_llm(cls, question: str, error_message: str) -> Optional[str]:
        """
        Use Haiku to rewrite a complex question into a simpler form.

        Args:
            question: Original user question
            error_message: Error from failed query attempt

        Returns:
            Simplified question or None if LLM fails
        """
        try:
            client = AnthropicBedrock(
                timeout=30.0,
                max_retries=1
            )

            prompt = f"""You are helping simplify a complex factory query that failed.

Original question: {question}

Error: {error_message}

Rewrite the question to be simpler and more direct while preserving the core intent. Follow these rules:

1. Replace complex phrases with simple terms:
   - "RNA/DNA synthesis equipment/instruments/machines" → "synthesizers" (do NOT add "RNA" or "DNA" prefix)
   - "not working/broken/down" → "offline"
   - "working/operational/available" → "online"

2. Remove ALL unnecessary words:
   - Politeness: "Can you please", "I need to know", "tell me about"
   - Temporal qualifiers: "currently", "right now", "at the moment"
   - Possessives: "our", "my", "the"
   - Type qualifiers: "RNA", "DNA", "oligo" (unless specifically filtering)

3. Use canonical patterns:
   - "show [status] [entity]" - e.g., "show offline synthesizers"
   - "show [entity]" - e.g., "show workflows"

4. Keep ONLY important filters:
   - Status (online/offline)
   - Dates ("last 30 days")
   - IDs (barcodes, work orders)

Return ONLY the simplified question, nothing else. Make it 2-4 words maximum."""

            response = client.messages.create(
                model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )

            simplified = response.content[0].text.strip()

            # Basic validation - don't return empty or overly long results
            if simplified and 2 <= len(simplified.split()) <= 10:
                return simplified.lower()

            return None

        except Exception as e:
            # LLM failed, will fall back to regex
            return None

    @classmethod
    def simplify_question(cls, question: str) -> str:
        """
        Simplify a complex question by normalizing phrases and extracting core intent.

        Args:
            question: Original user question

        Returns:
            Simplified version of the question
        """
        simplified = question.lower().strip()

        # Apply all phrase normalizations FIRST
        for pattern, replacement in cls.PHRASE_NORMALIZATIONS.items():
            simplified = re.sub(pattern, replacement, simplified, flags=re.IGNORECASE)

        # Remove complex sentence structures AGGRESSIVELY
        # "I need to know which X so I can Y" → "which X"
        # NOTE: Use word boundary after "so|that|because" to avoid matching "that's" as "that"
        simplified = re.sub(
            r'^.*?(?:I need to know|tell me (?:about|which)|show me|find|get)\s+(.*?)\s+(?:so|that|because)\b.*$',
            r'\1',
            simplified,
            flags=re.IGNORECASE
        )

        # "Can you tell me about X" → "Show X"
        simplified = re.sub(
            r'^(?:can|could|would|will|please)\s+(?:you\s+)?(?:tell me about|show me|find)\s+',
            'show ',
            simplified,
            flags=re.IGNORECASE
        )

        # Remove possessives ("our equipment" → "equipment")
        simplified = re.sub(r'\b(?:our|my|the)\s+', '', simplified, flags=re.IGNORECASE)

        # Remove filler words and temporal qualifiers
        simplified = re.sub(
            r'\b(?:currently|right now|at the moment|at this time|just|please|really|very|that\'?s?)\b',
            '',
            simplified,
            flags=re.IGNORECASE
        )

        # Remove redundant question marks and punctuation
        simplified = re.sub(r'[?!.]+$', '', simplified)

        # Clean up extra whitespace
        simplified = re.sub(r'\s+', ' ', simplified).strip()

        # If we've extracted a clear pattern, use canonical form
        # Pattern: "X that are/is Y" → "show Y X"
        canonical = cls._extract_canonical_query(simplified)
        if canonical:
            simplified = canonical

        return simplified

    @classmethod
    def _extract_canonical_query(cls, question: str) -> Optional[str]:
        """
        Extract canonical query form for common patterns.

        Args:
            question: Partially simplified question

        Returns:
            Canonical query string or None
        """
        q = question.lower().strip()

        # Pattern: "which/what synthesizers offline/online"
        if re.search(r'\b(?:which|what)\s+synthesizers?\s+(?:offline|online)', q):
            if 'offline' in q:
                return "show offline synthesizers"
            elif 'online' in q:
                return "show online synthesizers"

        # Pattern: "synthesizers offline/online"
        if 'synthesizers' in q:
            if 'offline' in q:
                return "show offline synthesizers"
            elif 'online' in q:
                return "show online synthesizers"
            else:
                return "show synthesizers"

        # Pattern: "workflows [with template name]"
        if 'workflows' in q:
            # Check for template names
            template_match = re.search(r'(?:template|named?|called)\s+([A-Za-z0-9\s]+)', q)
            if template_match:
                template = template_match.group(1).strip()
                return f"show workflows template {template}"
            elif 'offline' in q or 'down' in q:
                return "show offline workflows"
            elif 'online' in q or 'started' in q:
                return "show started workflows"
            else:
                return "show workflows"

        # Pattern: "instruments [type] offline/online"
        if 'instrument' in q:
            if 'offline' in q:
                return "show offline instruments"
            elif 'online' in q:
                return "show online instruments"
            else:
                return "show instruments"

        return None

    @classmethod
    def should_retry(cls, original_question: str, error_message: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if query should be retried with simplified question.

        Args:
            original_question: Original user question
            error_message: Error from failed query

        Returns:
            Tuple of (should_retry: bool, simplified_question: Optional[str])
        """
        # Check if error is recoverable
        if not cls.is_recoverable_error(error_message):
            return (False, None)

        # Try LLM-based simplification first (faster, smarter)
        simplified = cls.simplify_question_with_llm(original_question, error_message)

        # Fall back to regex-based simplification if LLM fails
        if not simplified:
            simplified = cls.simplify_question(original_question)

        # Only retry if simplification actually changed something significantly
        if simplified == original_question.lower().strip():
            return (False, None)

        return (True, simplified)

    @classmethod
    def extract_intent_keywords(cls, question: str) -> Dict[str, Any]:
        """
        Extract key intent components from a question for debugging.

        Args:
            question: User question

        Returns:
            Dict with detected entities, filters, and attributes
        """
        question_lower = question.lower()

        # Detect entity type
        entity = None
        if any(word in question_lower for word in ['synthesis', 'synthesizer', 'synth']):
            entity = 'synthesizer'
        elif any(word in question_lower for word in ['workflow', 'process', 'execution']):
            entity = 'workflow'
        elif any(word in question_lower for word in ['instrument', 'equipment', 'machine', 'printer', 'handler']):
            entity = 'instrument'

        # Detect status filters
        status = None
        if any(word in question_lower for word in ['down', 'broken', 'offline', 'failed', 'not working']):
            status = 'offline'
        elif any(word in question_lower for word in ['up', 'online', 'working', 'operational', 'available']):
            status = 'online'

        return {
            'entity': entity,
            'status': status,
            'original_question': question,
        }
