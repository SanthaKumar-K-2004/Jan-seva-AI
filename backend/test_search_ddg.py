
import asyncio
from duckduckgo_search import DDGS

async def test():
    print("Testing DDGS with backend='html'...")
    try:
        ddgs = DDGS()
        # backend='html', 'lite', 'auto'
        results = list(ddgs.text("Tamil Nadu Chief Minister", max_results=3, backend="html"))
        print(f"Results found: {len(results)}")
        for r in results:
            print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
