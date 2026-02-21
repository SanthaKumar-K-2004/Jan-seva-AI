import asyncio
import os
import sys

# Add backend to path (current directory if running from backend/)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.research_engine import ResearchEngine
from app.config import get_settings

async def main():
    print("🚀 Initializing Research Engine...")
    settings = get_settings()
    
    if not settings.groq_api_key:
        print("❌ GROQ_API_KEY is missing. Please set it in .env")
        return
        
    if not settings.tavily_api_key:
        print("⚠️ TAVILY_API_KEY is missing. Search will return empty results.")
    
    engine = ResearchEngine()
    query = "PM Vishwakarma Yojana benefits and eligibility"
    
    print(f"\n🧠 Researching: '{query}'...")
    result = await engine.research_scheme(query, language="en")
    
    print("\n" + "="*50)
    print("🤖 LLM ANSWER:")
    print("="*50)
    print(result["answer"])
    
    print("\n" + "="*50)
    print("🌐 SOURCES Found:")
    print("="*50)
    for s in result["sources"]:
        print(f"• {s['title']}")
        print(f"  {s['url']}")
        
    print("\n" + "="*50)
    print("🖼️ IMAGES Found:")
    print("="*50)
    for img in result["images"]:
        print(f"• {img}")

if __name__ == "__main__":
    asyncio.run(main())
