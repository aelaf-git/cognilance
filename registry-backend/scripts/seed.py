#!/usr/bin/env python3
"""Create an API key for SDK / agent development."""

from __future__ import annotations

import asyncio
import sys

from app.database import connect_db, disconnect_db, prisma
from app.services.api_keys import create_api_key


async def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "development"
    await connect_db()
    try:
        record, full_key = await create_api_key(prisma, name=name)
        print(f"API key created: {record.name}")
        print(f"ID:     {record.id}")
        print(f"Prefix: {record.keyPrefix}")
        print()
        print("Add to your .env:")
        print(f"COGNILANCE_API_KEY={full_key}")
        print()
        print("COGNILANCE_REGISTRY_URL=http://127.0.0.1:8088")
    finally:
        await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
