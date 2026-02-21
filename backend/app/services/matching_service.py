"""
Jan-Seva AI — Matching Service (Rule Engine)
Evaluates user profiles against scheme eligibility rules (JSON Logic).
"""
import json_logic
from typing import List, Dict, Any
from app.models.user import UserProfile
from app.core.supabase_client import get_supabase_client
from app.utils.logger import logger

class MatchingService:
    def __init__(self):
        self.supabase = get_supabase_client()

    async def match_profile(self, user_profile: UserProfile, limit: int = 20) -> List[Dict]:
        """
        Finds schemes that match the user's profile.
        1. Pre-filtering via DB query (State, Category).
        2. Strict filtering via JSON Logic Rule Engine.
        """
        user_data = user_profile.model_dump()
        
        # 1. Broad DB Filter
        # Fetch schemes where state is 'Central' OR user's state
        # And user's category (if any) is in scheme's beneficiary_type (heuristic)
        # For MVP, we fetch a larger set and filter in-memory
        try:
            query = self.supabase.table("schemes").select("*")\
                .or_(f"state.eq.Central,state.eq.{user_profile.state}")
            
            # TODO: Add more DB-level filtering optimization
            
            response = query.execute()
            candidates = response.data
        except Exception as e:
            logger.error(f"Failed to fetch schemes for matching: {e}")
            return []

        matches = []
        
        # 2. Rule Engine Execution
        for scheme in candidates:
            rules = scheme.get("eligibility_rules")
            
            if not rules:
                # If no structured rules, we might include it with a "Possible" flag
                # or skip it. For "Ultimate", let's include as "Potential Match"
                matches.append({**scheme, "match_confidence": "Software check unavailable (Manual Check Needed)"})
                continue
            
            try:
                # Normalize user data for logic engine
                # e.g., ensure 'age', 'income' are numbers
                from json_logic import jsonLogic
                is_eligible = jsonLogic(rules, user_data)
                
                if is_eligible:
                    matches.append({**scheme, "match_confidence": "High (Verified by Rule Engine)"})
            except Exception as e:
                logger.warning(f"Rule evaluation failed for scheme {scheme.get('name')}: {e}")
        
        # Sort by confidence
        # matches.sort(key=lambda x: x["match_confidence"], reverse=True)
        return matches[:limit]

# Singleton
_matcher = None

def get_matching_service():
    global _matcher
    if _matcher is None:
        _matcher = MatchingService()
    return _matcher
