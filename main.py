#!/usr/bin/env python3
"""Property Finder — scrape estate agents and email daily digests."""

import argparse
import asyncio
import sys

import yaml

from scrapers import AGENT_REGISTRY


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def cmd_scrape(config: dict):
    """Run all scrapers, deduplicate, update state."""
    from dedup import load_state, save_state, get_new_properties

    state = load_state()
    all_new = []

    for search in config["searches"]:
        agent_name = search["agent"]
        scraper_cls = AGENT_REGISTRY.get(agent_name)
        if not scraper_cls:
            print(f"Unknown agent: {agent_name}", file=sys.stderr)
            continue

        scraper = scraper_cls()
        print(f"Scraping {agent_name} for '{search['name']}'...")
        properties = await scraper.scrape(search)
        print(f"  Found {len(properties)} listings")

        if "boundary" in search:
            from geocoder import geocode_properties
            from geofilter import filter_by_boundary
            properties = geocode_properties(properties)
            properties = filter_by_boundary(properties, search["boundary"])
            print(f"  {len(properties)} within boundary")

        new = get_new_properties(properties, state)
        print(f"  {len(new)} new listings")
        all_new.extend(new)

    # Update state with all new properties
    for prop in all_new:
        state[prop.id] = {
            "first_seen": prop.first_seen,
            "last_seen": prop.first_seen,
            "emailed": False,
            "property": prop.to_dict(),
        }

    save_state(state)
    print(f"\nTotal new properties: {len(all_new)}")


async def cmd_digest(config: dict):
    """Score unsent properties and send email digest."""
    from dedup import load_state, save_state
    from emailer import send_digest
    from models import Property

    state = load_state()
    unsent = [
        Property.from_dict(entry["property"])
        for entry in state.values()
        if not entry["emailed"]
    ]

    if not unsent:
        print("No new properties to send.")
        return

    # Sort by price ascending for now (v1 — no scoring)
    unsent.sort(key=lambda p: p.price)

    email_config = config["email"]
    send_digest(unsent, email_config)
    print(f"Sent digest with {len(unsent)} properties.")

    # Mark as emailed
    for prop in unsent:
        if prop.id in state:
            state[prop.id]["emailed"] = True
    save_state(state)


async def cmd_inspect(config: dict, agent_name: str):
    """Dump rendered DOM for a search page (debugging)."""
    scraper_cls = AGENT_REGISTRY.get(agent_name)
    if not scraper_cls:
        print(f"Unknown agent: {agent_name}", file=sys.stderr)
        return

    # Find a matching search config
    search = next(
        (s for s in config["searches"] if s["agent"] == agent_name),
        None,
    )
    if not search:
        print(f"No search config found for agent: {agent_name}", file=sys.stderr)
        return

    scraper = scraper_cls()
    await scraper.inspect(search)


def main():
    parser = argparse.ArgumentParser(description="Property Finder")
    parser.add_argument(
        "command",
        choices=["scrape", "digest", "scrape+digest", "inspect"],
        help="Command to run",
    )
    parser.add_argument(
        "agent",
        nargs="?",
        help="Agent name (required for inspect)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.command == "scrape":
        asyncio.run(cmd_scrape(config))
    elif args.command == "digest":
        asyncio.run(cmd_digest(config))
    elif args.command == "scrape+digest":
        asyncio.run(cmd_scrape(config))
        asyncio.run(cmd_digest(config))
    elif args.command == "inspect":
        if not args.agent:
            print("Usage: main.py inspect <agent>", file=sys.stderr)
            sys.exit(1)
        asyncio.run(cmd_inspect(config, args.agent))


if __name__ == "__main__":
    main()
