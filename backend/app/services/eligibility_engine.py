"""
Jan-Seva AI — Eligibility Engine (Enhanced)
The GUARD. JSON rule matching + LLM "Why Not?" explainer + alternative suggestions.
"""

from app.core.supabase_client import get_supabase_client
from app.core.llm_client import get_llm_client
from app.models.chat import EligibilityResponse
from app.utils.logger import logger


class EligibilityEngine:
    """
    Hybrid Eligibility Checker:
    1. Hard Rules: JSON-based logic (age < max, income < limit)
    2. LLM "Why Not?" Explainer: Always explains in simple language
    3. Alternative Finder: Ranks similar schemes by match score
    """

    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "lt": lambda a, b: a < b,
        "gt": lambda a, b: a > b,
        "lte": lambda a, b: a <= b,
        "gte": lambda a, b: a >= b,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
        "contains": lambda a, b: b in str(a),
        "between": lambda a, b: b[0] <= a <= b[1] if isinstance(b, list) and len(b) == 2 else False,
    }

    async def check(self, scheme_id: str, user_profile: dict) -> EligibilityResponse:
        """
        Check eligibility for a single scheme.
        Returns detailed result with reason, score, and alternatives.
        """
        client = get_supabase_client()

        # Get scheme details
        scheme = client.table("schemes").select("*").eq("id", scheme_id).single().execute()
        scheme_data = scheme.data

        # Get eligibility rules
        rules = client.table("eligibility_rules").select("*").eq("scheme_id", scheme_id).execute()
        rules_data = rules.data

        # Run rule checks
        passed = []
        failed = []
        total_rules = len(rules_data)

        for rule in rules_data:
            result = self._check_rule(rule, user_profile)
            if result["passed"]:
                passed.append({"criteria": rule["rule_type"], "description": rule.get("description", "")})
            else:
                failed.append({
                    "criteria": rule["rule_type"],
                    "reason": result["reason"],
                    "description": rule.get("description", ""),
                })

        is_eligible = len(failed) == 0
        match_score = int((len(passed) / max(total_rules, 1)) * 100)

        # Build human-friendly explanation
        if is_eligible:
            reason = (
                f"✅ Great news! You are eligible for **{scheme_data['name']}**! "
                f"You meet all {total_rules} criteria.\n\n"
                f"**Benefits:** {scheme_data.get('benefits', 'See scheme details')}\n\n"
                f"📞 Apply at: {scheme_data.get('source_url', 'Check official portal')}"
            )
        else:
            reason_lines = [
                f"❌ {f['criteria']}: {f['reason']}" for f in failed
            ]
            passed_lines = [
                f"✅ {p['criteria']}: Met" for p in passed
            ]
            reason = (
                f"You are not currently eligible for **{scheme_data['name']}**.\n\n"
                f"**What you qualify for:**\n" + "\n".join(passed_lines) + "\n\n"
                f"**What you don't meet:**\n" + "\n".join(reason_lines)
            )

        # Generate LLM "Why Not?" explanation for failed cases
        why_not_explanation = ""
        if not is_eligible and failed:
            why_not_explanation = await self._generate_why_not(
                scheme_data, user_profile, passed, failed
            )
            if why_not_explanation:
                reason += f"\n\n💡 **What you can do:**\n{why_not_explanation}"

        # Find alternatives if not eligible
        alternatives = []
        if not is_eligible:
            alternatives = await self._find_alternatives(
                user_profile, scheme_data.get("category", []), scheme_id
            )

        return EligibilityResponse(
            scheme_id=scheme_id,
            scheme_name=scheme_data["name"],
            is_eligible=is_eligible,
            match_score=match_score,
            reason=reason,
            missing_criteria=[f["criteria"] for f in failed],
            alternatives=alternatives,
        )

    def _check_rule(self, rule: dict, profile: dict) -> dict:
        """Check a single eligibility rule against user profile."""
        rule_type = rule["rule_type"]
        operator = rule["operator"]
        value = rule["value"]

        user_value = profile.get(rule_type)

        # If user didn't provide this field, we can't check
        if user_value is None:
            return {"passed": False, "reason": f"Missing: Please provide your {rule_type}."}

        # Handle range values (e.g., {"min": 18, "max": 60})
        if isinstance(value, dict) and "min" in value and "max" in value:
            if value["min"] <= user_value <= value["max"]:
                return {"passed": True, "reason": ""}
            return {
                "passed": False,
                "reason": (
                    f"Your {rule_type} is {user_value}, "
                    f"but must be between {value['min']}-{value['max']}."
                ),
            }

        # Handle list values (e.g., ["SC", "ST", "OBC"])
        if isinstance(value, list):
            op_func = self.OPERATORS.get(operator, self.OPERATORS["in"])
            if op_func(user_value, value):
                return {"passed": True, "reason": ""}
            return {
                "passed": False,
                "reason": (
                    f"Your {rule_type} is '{user_value}', "
                    f"but must be one of: {', '.join(map(str, value))}."
                ),
            }

        # Handle simple comparison
        op_func = self.OPERATORS.get(operator)
        if op_func and op_func(user_value, value):
            return {"passed": True, "reason": ""}

        return {
            "passed": False,
            "reason": f"Your {rule_type} is {user_value}, but the requirement is {operator} {value}.",
        }

    async def _generate_why_not(
        self, scheme_data: dict, profile: dict, passed: list, failed: list
    ) -> str:
        """Use LLM to generate empathetic 'Why Not?' explanation with actionable advice."""
        try:
            llm = get_llm_client()
            result = await llm.generate_eligibility(
                user_profile=profile,
                rules=[
                    {"status": "passed", "criteria": p["criteria"]} for p in passed
                ] + [
                    {"status": "failed", "criteria": f["criteria"], "reason": f["reason"]}
                    for f in failed
                ],
            )
            return result
        except Exception as e:
            logger.warning(f"Why Not? LLM explanation failed: {e}")
            # Fallback: simple textual advice
            tips = []
            for f in failed:
                criteria = f["criteria"]
                if "age" in criteria:
                    tips.append("• Wait until you meet the age requirement, or check if there are similar schemes for your age group.")
                elif "income" in criteria:
                    tips.append("• Look for schemes with higher income limits, or check if your family qualifies under a different category.")
                elif "caste" in criteria or "category" in criteria:
                    tips.append("• Check general category schemes or schemes specific to your community.")
                elif "state" in criteria:
                    tips.append("• This scheme may be state-specific. Check your own state's equivalent scheme.")
                else:
                    tips.append(f"• Check if your {criteria} can be updated or if there are exceptions.")
            return "\n".join(tips) if tips else ""

    async def _find_alternatives(
        self, profile: dict, categories: list, exclude_id: str = None
    ) -> list[dict]:
        """Find alternative schemes the user IS or might be eligible for."""
        client = get_supabase_client()

        try:
            # Get schemes in same categories
            query = client.table("schemes").select(
                "id, name, benefits, category, state"
            ).eq("is_active", True)

            if categories:
                query = query.overlaps("category", categories)

            alternatives_raw = query.limit(10).execute()

            results = []
            for s in alternatives_raw.data:
                if s["id"] == exclude_id:
                    continue
                results.append({
                    "id": s["id"],
                    "name": s["name"],
                    "benefits": s.get("benefits", ""),
                    "state": s.get("state", "Central"),
                })
                if len(results) >= 5:
                    break

            return results
        except Exception as e:
            logger.error(f"Failed to find alternatives: {e}")
            return []

    async def find_matching_schemes(self, profile: dict) -> list[dict]:
        """Find ALL schemes matching a user profile with scoring."""
        client = get_supabase_client()
        all_schemes = client.table("schemes").select("id, name, benefits").eq("is_active", True).execute()

        results = []
        for scheme in all_schemes.data[:50]:  # Limit to avoid timeout
            try:
                result = await self.check(scheme["id"], profile)
                results.append({
                    "scheme_id": scheme["id"],
                    "scheme_name": scheme["name"],
                    "benefits": scheme.get("benefits", ""),
                    "is_eligible": result.is_eligible,
                    "match_score": result.match_score,
                    "reason": result.reason,
                })
            except Exception:
                continue

        # Sort by match score (highest first)
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results


# --- Singleton ---
_engine: EligibilityEngine | None = None


def get_eligibility_engine() -> EligibilityEngine:
    """Returns a cached Eligibility Engine instance."""
    global _engine
    if _engine is None:
        _engine = EligibilityEngine()
    return _engine
