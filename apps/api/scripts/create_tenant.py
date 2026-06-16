"""Provision a tenant and print a fresh API key (shown exactly once).

Usage:
    python -m scripts.create_tenant --name "Acme Health" --slug acme-health

The raw key is never stored; only its SHA-256 hash and a non-secret prefix are
persisted. Copy the key from the output — it cannot be recovered later.
"""
import argparse
import asyncio

from src.core.auth import generate_api_key, hash_api_key, key_prefix
from src.db.session import async_session
from src.models.tenant import Tenant


async def create_tenant(name: str, slug: str, plan: str) -> str:
    raw_key = generate_api_key()
    async with async_session() as session:
        tenant = Tenant(
            name=name,
            slug=slug,
            plan=plan,
            api_key_hash=hash_api_key(raw_key),
            api_key_prefix=key_prefix(raw_key),
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
    print(f"Tenant created: {tenant.id} ({name})")
    print(f"API key (store this now, it will not be shown again):\n  {raw_key}")
    return raw_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an AgentShield tenant + API key")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--slug", required=True, help="Unique slug")
    parser.add_argument("--plan", default="discover", help="Plan tier (default: discover)")
    args = parser.parse_args()
    asyncio.run(create_tenant(args.name, args.slug, args.plan))


if __name__ == "__main__":
    main()
