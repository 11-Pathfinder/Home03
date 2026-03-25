"""Filter properties by geographic boundary (point-in-polygon)."""

from __future__ import annotations

from models import Property


def point_in_polygon(lng: float, lat: float, polygon: list[list[float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test.

    polygon: list of [lng, lat] pairs defining the boundary.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def filter_by_boundary(properties: list[Property], boundary: list[list[float]]) -> list[Property]:
    """Keep properties within the boundary polygon.

    Properties that couldn't be geocoded are included (not silently dropped).
    boundary: list of [lng, lat] pairs.
    """
    filtered = []
    for prop in properties:
        if prop.lat is None or prop.lng is None:
            # Can't geo-filter — include by default
            filtered.append(prop)
        elif point_in_polygon(prop.lng, prop.lat, boundary):
            filtered.append(prop)
    return filtered
