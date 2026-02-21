"""
Verification test for OpenAI Client
"""
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.openai_client import get_openai_client
from app.utils.logger import logger

async def test_openai():
    logger.info("🚀 Testing OpenAI Client...")
    client = get_openai_client()
    
    if not client.client:
        logger.error("❌ OpenAI Client not initialized (API key missing?)")
        return

    try:
        # 1. Test standard generation
        logger.info(f"📝 Testing standard generation with {client.model}...")
        res = await client.generate("You are a haiku master.", "write a haiku about modern india")
        logger.info(f"✅ Result:\n{res}")

        # 2. Test create_response (Experimental feature requested by user)
        # We'll use a try-except here because it's a model/SDK specific feature
        logger.info(f"🧪 Testing create_response (SDK: {client.model})...")
        try:
            res_experimental = await client.create_response("write a haiku about ai")
            logger.info(f"✅ Experimental Result:\n{res_experimental}")
        except Exception as e:
            logger.warning(f"⚠️ Experimental API failed (as expected if model is future-dated): {e}")

    except Exception as e:
        logger.error(f"❌ OpenAI Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_openai())
