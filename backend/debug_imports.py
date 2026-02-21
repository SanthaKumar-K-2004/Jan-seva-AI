import sys
import os
sys.path.insert(0, os.getcwd())

try:
    print("1. Importing BaseModel...")
    from pydantic import BaseModel
    print("2. Importing SearchResult...")
    from app.services.research.search_service import SearchResult, ResearchResponse
    print("3. Instantiating SearchResult...")
    s = SearchResult(title="Test", url="http://test.com", content="content")
    print("4. Instantiating ResearchResponse...")
    r = ResearchResponse(results=[s])
    print("5. Importing TavilySearchProvider...")
    from app.services.research.tavily_provider import TavilySearchProvider
    print("6. Instantiating TavilySearchProvider...")
    t = TavilySearchProvider()
    print("✅ All imports and instantiations successful.")
except Exception as e:
    import traceback
    with open("debug_error.txt", "w") as f:
        traceback.print_exc(file=f)
    print("❌ Error captured in debug_error.txt")
