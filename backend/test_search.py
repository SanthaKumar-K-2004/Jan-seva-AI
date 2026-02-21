
import sys
import os
sys.path.append(os.getcwd())

import asyncio
from app.services.web_search_service import get_web_search_service

# Force UTF-8 encoding for stdout/stderr to handle emojis if possible
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

async def test():
    try:
        service = get_web_search_service()
        
        # Test 1: Simple query
        query1 = "Tamil Nadu Chief Minister"
        print(f"Test 1: Searching for: {query1}")
        results1 = await service.search(query1)
        if results1:
            print("Results found (length:", len(results1), ")")
        else:
            print("No results found for simple query.")

        print("-" * 20)

        # Test 2: User query
        query2 = "Ulagam Ungal Kaiyil scheme 2026"
        print(f"Test 2: Searching for: {query2}")
        results2 = await service.search(query2)
        if results2:
            print("Results found (length:", len(results2), ")")
            print(results2[:500] + "...") # Print first 500 chars
        else:
            print("No results found for user query.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
