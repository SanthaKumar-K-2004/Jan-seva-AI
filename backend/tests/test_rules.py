import pytest
import json
from app.models.user import UserProfile
from app.services.matching_service import MatchingService
# mock supabase for testing
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_supabase():
    with patch('app.services.matching_service.get_supabase_client') as mock:
        yield mock

@pytest.fixture
def matching_service(mock_supabase):
    return MatchingService()

def test_json_logic_evaluation():
    """Test basic JSON logic evaluation independent of service."""
    from json_logic import jsonLogic
    
    rules = {"and": [{">=": [{"var": "age"}, 18]}, {"<": [{"var": "income"}, 200000]}]}
    
    eligible = {"age": 20, "income": 100000}
    ineligible_age = {"age": 16, "income": 100000}
    ineligible_income = {"age": 20, "income": 300000}
    
    assert jsonLogic(rules, eligible) is True
    assert jsonLogic(rules, ineligible_age) is False
    assert jsonLogic(rules, ineligible_income) is False

@pytest.mark.asyncio
async def test_matching_service_logic(matching_service, mock_supabase):
    """Test the MatchingService filter logic."""
    
    # Mock Scheme Data
    mock_schemes = [
        {
            "id": "1",
            "name": "Youth Scheme",
            "state": "Central",
            "eligibility_rules": {">=": [{"var": "age"}, 18]}
        },
        {
            "id": "2", 
            "name": "Senior Scheme",
            "state": "Central",
            "eligibility_rules": {">=": [{"var": "age"}, 60]}
        }
    ]
    
    # Setup mock return
    mock_response = MagicMock()
    mock_response.data = mock_schemes
    mock_supabase.return_value.table.return_value.select.return_value.or_.return_value.execute.return_value = mock_response

    # Test User (Age 25) -> Should match Scheme 1 only
    user = UserProfile(age=25, name="Young User", state="Delhi")
    matches = await matching_service.match_profile(user)
    
    assert len(matches) == 1
    assert matches[0]["id"] == "1"
    assert matches[0]["match_confidence"] == "High (Verified by Rule Engine)"
    
    # Test User (Age 65) -> Should match both (assuming >18 matches 65)
    user_senior = UserProfile(age=65, name="Senior User", state="Delhi")
    matches_senior = await matching_service.match_profile(user_senior)
    
    assert len(matches_senior) == 2
