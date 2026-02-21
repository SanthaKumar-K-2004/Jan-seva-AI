"""
Jan-Seva AI — Analytics Service
Provides deep insights, gap analysis, and cross-department comparisons.
"""
from typing import List, Dict
from app.core.supabase_client import get_supabase_client
from app.core.llm_client import get_llm_client
from app.utils.logger import logger

class AnalyticsService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.llm = get_llm_client()

    async def compare_schemes(self, scheme_ids: List[str]) -> str:
        """
        Generates a side-by-side comparison of multiple schemes.
        returns: Markdown report.
        """
        # Fetch scheme details
        response = self.supabase.table("schemes").select("*").in_("id", scheme_ids).execute()
        schemes = response.data
        
        if not schemes:
            return "No schemes found to compare."

        # Construct comparison prompt
        scheme_context = ""
        for s in schemes:
            scheme_context += f"Scheme: {s['name']}\nBenefits: {s.get('benefits')}\nEligibility: {s.get('eligibility_rules', 'N/A')}\n\n"

        prompt = (
            "Compare the following government schemes. \n"
            "Create a comparison table highlighting:\n"
            "1. Benefits Magnitude\n"
            "2. Ease of Access (Documents needed)\n"
            "3. Target Audience overlaps\n"
            "4. Recommendation (Which is better for whom?)\n\n"
            f"{scheme_context}"
        )

        return await self.llm.generate(prompt, context="You are a precise policy analyst.", chat_history=[])

    async def gap_analysis(self, sector: str, state: str) -> dict:
        """
        Identifies missing coverage in a sector for a specific state vs central/others.
        """
        # 1. Fetch schemes for this state+sector
        state_schemes = self.supabase.table("schemes")\
            .select("name, beneficiary_type")\
            .eq("state", state)\
            .contains("category", [sector])\
            .execute().data
            
        # 2. Fetch Central schemes for same sector
        central_schemes = self.supabase.table("schemes")\
            .select("name, beneficiary_type")\
            .eq("state", "Central")\
            .contains("category", [sector])\
            .execute().data

        # 3. Analyze coverage
        beneficiaries_covered = set()
        for s in state_schemes + central_schemes:
            for b in s.get("beneficiary_type", []):
                beneficiaries_covered.add(b.lower())
        
        # 4. Use LLM to identify gaps
        summary = f"State: {state}, Sector: {sector}\n"
        summary += f"Covered Groups: {list(beneficiaries_covered)}\n"
        summary += f"Total Schemes: {len(state_schemes)} (State) + {len(central_schemes)} (Central)"
        
        prompt = (
            f"Analyze this data:\n{summary}\n"
            "Identify 3 key demographic groups that are likely UNDER-SERVED or missing coverage in this sector. "
            "Return JSON: {\"missing_groups\": [\"group1\", \"group2\"], \"insight\": \"...\"}"
        )
        
        response = await self.llm.generate(prompt, context="You are a social welfare data scientist.", chat_history=[])
        return response # Expecting JSON string, ignoring parsing for brevity here

# Singleton
_analytics = None

def get_analytics_service():
    global _analytics
    if _analytics is None:
        _analytics = AnalyticsService()
    return _analytics
