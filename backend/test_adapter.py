import asyncio
from app.services.metaapi_service import get_symbol_specification

async def main():
    spec = await get_symbol_specification('e496a759-9b7e-46bd-acd8-3add8fe030e2', 'BTCUSD')
    print("Spec:", spec.get("digits"), spec.get("point"), spec.get("stopLevel"), spec.get("spread"))

asyncio.run(main())
