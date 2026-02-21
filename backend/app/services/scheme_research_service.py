"""
Scheme Research Service
Uses Web Search (Google/DDG) + NVIDIA Qwen 3.5 to create a comprehensive scheme report.
"""
import json
import asyncio
from app.core.nvidia_client import get_nvidia_client
from app.services.web_search_service import get_web_search_service
from app.utils.logger import logger

class SchemeResearchService:
    def __init__(self):
        self.nvidia = get_nvidia_client()
        self.web_search = get_web_search_service()
        self.parser = None  # Lazy load to avoid circular imports if any

    def _get_parser(self):
        if self.parser is None:
            from app.services.scheme_parser import get_scheme_parser
            self.parser = get_scheme_parser()
        return self.parser

    async def research_scheme(self, scheme_name: str) -> dict:
        """
        Deep research for a specific scheme.
        1. Search web for detailed info.
        2. Use Qwen 3.5 to extract structured JSON.
        """
        try:
            # 1. Broad Web Search
            search_query = f"{scheme_name} official guidelines details benefits eligibility application process 2025 2026"
            web_context = await self.web_search.search(search_query, limit=6)
            
            if not web_context:
                logger.warning(f"Research aborted: No web info found for '{scheme_name}'")
                return {"error": "No information found on the web."}

            # 2. NVIDIA Qwen 3.5 Analysis
            system_prompt = (
                "You are an expert Government Scheme Researcher. "
                "Your task is to analyze raw web search results and extract structured information about a specific government scheme. "
                "Output ONLY valid JSON matching the specified schema. Do not output markdown code blocks."
            )
            
            user_prompt = f"""
            Analyze the following information about the scheme: **{scheme_name}**.
            
            RAW WEB DATA:
            {web_context}
            
            TASK:
            Extract the following details into a JSON object:
            {{
                "name": "Exact official name",
                "launched_by": "State or Central Govt name",
                "launch_year": "YYYY (or 'Unknown')",
                "description": "Brief summary (2-3 sentences)",
                "eligibility": ["Rule 1", "Rule 2", ...],
                "benefits": ["Benefit 1", "Benefit 2", ...],
                "documents_required": ["Doc 1", "Doc 2", ...],
                "application_process": ["Step 1", "Step 2", ...],
                "official_website": "URL or 'Unknown'"
            }}
            
            If a field is not found in the text, use "Unknown" or empty list [].
            Ensure the output is pure JSON.
            """
            
            # 3. Call Generative AI
            llm_response = await self.nvidia.generate(system_prompt, user_prompt, temperature=0.3)
            
            # 4. Clean and Parse JSON
            # Remove markdown fences if present
            cleaned_json = llm_response.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]
            
            try:
                data = json.loads(cleaned_json)
                data["sources"] = "Web Search + NVIDIA Qwen 3.5 Analysis"
                
                # 5. [NEW] Structure Eligibility Rules
                if "eligibility" in data:
                    eligibility_text = json.dumps(data["eligibility"]) if isinstance(data["eligibility"], list) else str(data["eligibility"])
                    try:
                        parser = self._get_parser()
                        rules = await parser.parse_to_json_logic(eligibility_text)
                        data["eligibility_rules"] = rules
                        logger.info(f"Structured rules for {scheme_name}: {rules}")
                    except Exception as e:
                        logger.warning(f"Failed to structure rules: {e}")
                        data["eligibility_rules"] = {}

                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse NVIDIA response as JSON: {llm_response}")
                return {
                    "error": "Failed to parse analysis results.", 
                    "raw_response": llm_response
                }

        except Exception as e:
            logger.error(f"Scheme research failed: {e}")
            return {"error": str(e)}

# Singleton
_research_service = None

def get_research_service():
    global _research_service
    if _research_service is None:
        _research_service = SchemeResearchService()
    return _research_service
