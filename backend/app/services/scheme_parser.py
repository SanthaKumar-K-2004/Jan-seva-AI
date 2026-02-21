"""
Jan-Seva AI — Scheme Parser Service
Converts raw scheme text into structured JSON Logic for the Rule Engine.
"""
import json
import re
from typing import Dict, Any
from app.core.llm_client import get_llm_client
from app.utils.logger import logger

class SchemeParser:
    def __init__(self):
        self.llm = get_llm_client()

    async def parse_to_json_logic(self, scheme_text: str) -> Dict[str, Any]:
        """
        Uses LLM to extract eligibility criteria as standardized JSON Logic.
        """
        system_prompt = (
            "You are a Logic Engineer for a Government Scheme Engine. "
            "Your task is to convert eligibility text into strict JSON Logic format."
            "\n\n"
            "Supported Variables (use EXACT case):\n"
            "- age (number)\n"
            "- income (number, annual in INR)\n"
            "- gender (string: 'Male', 'Female', 'Transgender', 'All')\n"
            "- category (string: 'General', 'OBC', 'SC', 'ST')\n"
            "- state (string: State Name)\n"
            "- occupation (string)\n"
            "- caste (string)\n"
            "- is_student (boolean)\n"
            "- is_farmer (boolean)\n"
            "- is_disabled (boolean)\n"
            "\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY a JSON object representing the logic. No markdown, no comments.\n"
            "Example:\n"
            "{\"and\": [\n"
            "  {\">=\": [{\"var\": \"age\"}, 18]},\n"
            "  {\"<\": [{\"var\": \"income\"}, 200000]}\n"
            "]}"
        )

        user_prompt = f"Convert this eligibility criteria to JSON Logic:\n\n{scheme_text}"

        try:
            response = await self.llm.generate(
                user_query=user_prompt,
                context=system_prompt, # Using context arg for system prompt
                chat_history=[],
                language="en"
            )
            
            return self._clean_json(response)
        except Exception as e:
            logger.error(f"SchemeParser Error: {e}")
            return {}

    async def parse_graph_relations(self, scheme_text: str, known_schemes: list[str]) -> Dict[str, list]:
        """
        Identifies relationships to other schemes.
        """
        # Placeholder for future implementation
        return {"related": [], "prerequisite": []}

    def _clean_json(self, raw_text: str) -> Dict[str, Any]:
        """Sanitizes LLM output to valid JSON."""
        try:
            # Remove markdown code blocks if present
            cleaned = re.sub(r"```json\s*|\s*```", "", raw_text, flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON Logic: {raw_text[:50]}...")
            return {}

# Singleton
_parser = None

def get_scheme_parser():
    global _parser
    if _parser is None:
        _parser = SchemeParser()
    return _parser
