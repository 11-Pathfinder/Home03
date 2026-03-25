"""Geocode UK postcodes via postcodes.io (free, no API key)."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from models import Property

CACHE_PATH = Path("data/postcode_cache.json")
BULK_URL = "https://api.postcodes.io/postcodes"
OUTCODE_URL = "https://api.postcodes.io/outcodes/{}"

# Full UK postcode: e.g. SW19 4EU, KT3 3NX
_FULL_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.IGNORECASE)
# Outcode only: e.g. KT3, SW19
_OUTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\b", re.IGNORECASE)


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def extract_postcode(address: str) -> str | None:
    """Extract a UK postcode from an address string."""
    m = _FULL_RE.search(address)
    if m:
        return m.group(1).strip().upper()
    m = _OUTCODE_RE.search(address)
    if m:
        return m.group(1).strip().upper()
    return None


def _bulk_lookup(postcodes: list[str]) -> dict[str, tuple[float, float]]:
    """Batch lookup full postcodes via postcodes.io (max 100 per request)."""
    results = {}
    for i in range(0, len(postcodes), 100):
        batch = postcodes[i : i + 100]
        data = json.dumps({"postcodes": batch}).encode()
        req = urllib.request.Request(
            BULK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        for item in body.get("result", []):
            if item["result"]:
                r = item["result"]
                results[item["query"].upper()] = (r["latitude"], r["longitude"])
    return results


def _outcode_lookup(outcode: str) -> tuple[float, float] | None:
    """Look up an outcode (e.g. KT3) for its centroid."""
    url = OUTCODE_URL.format(outcode)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = json.loads(resp.read())
        if body.get("result"):
            r = body["result"]
            return (r["latitude"], r["longitude"])
    except Exception:
        pass
    return None


def geocode_properties(properties: list[Property]) -> list[Property]:
    """Add lat/lng to properties by geocoding their postcodes."""
    cache = _load_cache()

    # Extract postcodes and identify which need lookup
    prop_postcodes: list[tuple[int, str]] = []  # (index, postcode)
    full_to_lookup: list[str] = []
    outcode_to_lookup: list[str] = []

    for i, prop in enumerate(properties):
        if prop.lat is not None:
            continue
        pc = extract_postcode(prop.address)
        if not pc:
            continue
        prop_postcodes.append((i, pc))
        if pc in cache:
            continue
        if _FULL_RE.match(pc):
            full_to_lookup.append(pc)
        else:
            outcode_to_lookup.append(pc)

    # Bulk lookup full postcodes
    if full_to_lookup:
        results = _bulk_lookup(list(set(full_to_lookup)))
        cache.update({k: list(v) for k, v in results.items()})

    # Individual lookup outcodes
    for oc in set(outcode_to_lookup):
        if oc not in cache:
            coords = _outcode_lookup(oc)
            if coords:
                cache[oc] = list(coords)

    _save_cache(cache)

    # Apply coordinates to properties
    for i, pc in prop_postcodes:
        if pc in cache:
            properties[i].lat = cache[pc][0]
            properties[i].lng = cache[pc][1]

    geocoded = sum(1 for p in properties if p.lat is not None)
    print(f"  Geocoded {geocoded}/{len(properties)} properties")
    return properties
