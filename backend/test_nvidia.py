import asyncio
from app.core.nvidia_client import get_nvidia_client

async def test():
    nvidia = get_nvidia_client()
    result = await nvidia.generate(
        system="Return ONLY valid JSON.",
        user_query='List 3 Indian education schemes as a JSON array with name and ministry fields.',
        temperature=0.3,
    )
    print("OK:", result[:500])

asyncio.run(test())
