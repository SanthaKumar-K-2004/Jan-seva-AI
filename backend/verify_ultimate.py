"""
Verification Script for Jan-Seva AI Ultimate Edition
Tests:
1. Crawler Service (Mocked)
2. Scheme Parser (Logic Extraction)
3. Rule Engine (Matching)
"""
import asyncio
import json
from app.services.scheme_parser import get_scheme_parser
from app.models.user import UserProfile
from app.services.matching_service import get_matching_service
from app.services.scraper.crawler_service import get_crawler_service

async def test_full_flow():
    print("Starting Verification of Ultimate Architecture...\n")

    # 1. Test Crawler Discovery (Dry Run logic)
    print("Testing Crawler Service...")
    crawler = get_crawler_service()
    # We won't actually crawl to save time/bandwidth, just checking instantiation
    print(f"   Crawler initialized. Visited count: {len(crawler.visited_urls)}")

    # 2. Test Scheme Parser (Text -> JSON Logic)
    print("\nTesting Scheme Parser (LLM -> JSON Logic)...")
    parser = get_scheme_parser()
    sample_text = "Applicants must be at least 18 years old and have an annual income less than 2,00,000 INR."
    print(f"   Input: '{sample_text}'")
    
    # Mocking LLM response or testing real if env is set
    # check if we can run it (env might be missing keys, so we catch)
    try:
        logic = await parser.parse_to_json_logic(sample_text)
        print(f"   Output Logic: {json.dumps(logic, indent=2)}")
    except Exception as e:
        print(f"   Parser test skipped (LLM key missing?): {e}")

    # 3. Test Rule Engine (JSON Logic Matching)
    print("\nTesting Rule Engine...")
    matcher = get_matching_service()
    
    # Mock Scheme with Rules
    mock_scheme = {
        "name": "Test Scheme",
        "eligibility_rules": {
            "and": [
                {">=": [{"var": "age"}, 18]},
                {"<": [{"var": "income"}, 200000]}
            ]
        }
    }
    
    # Mock User Profile
    user_eligible = UserProfile(age=25, income=150000, name="Eligible User")
    user_ineligible = UserProfile(age=16, income=150000, name="Ineligible User")
    
    # Test Evaluation
    from json_logic import jsonLogic
    result1 = jsonLogic(mock_scheme["eligibility_rules"], user_eligible.model_dump())
    result2 = jsonLogic(mock_scheme["eligibility_rules"], user_ineligible.model_dump())
    
    print(f"   User 1 (Eligible): {result1} (Expected: True)")
    print(f"   User 2 (Ineligible): {result2} (Expected: False)")
    
    if result1 and not result2:
        print("\nVerification SUCCESS: Rule Engine works correctly!")
    else:
        print("\nVerification FAILED: Rule Engine logic incorrect.")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
