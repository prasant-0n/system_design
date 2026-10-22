"""
Geospatial Indexing Lab:
1. Geohash Encoder/Decoder (Base32 Bit-Interleaving)
2. 2D Point QuadTree with Haversine Radius Querying
"""

import math
from typing import Any, List, Optional, Tuple


# -------------------------------------------------------------
# 1. Geohash Implementation
# -------------------------------------------------------------

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
BASE32_MAP = {char: i for i, char in enumerate(BASE32)}


def geohash_encode(lat: float, lon: float, precision: int = 6) -> str:
    """
    Encodes (latitude, longitude) into a Base32 Geohash string.
    Interleaves longitude (even bits) and latitude (odd bits).
    """
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("Latitude must be in [-90, 90], Longitude in [-180, 180]")

    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]

    geohash = []
    bits = 0
    ch = 0
    is_even = True

    while len(geohash) < precision:
        if is_even:
            # Bisect longitude
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon >= mid:
                ch = (ch << 1) | 1
                lon_interval[0] = mid
            else:
                ch = (ch << 1) | 0
                lon_interval[1] = mid
        else:
            # Bisect latitude
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat >= mid:
                ch = (ch << 1) | 1
                lat_interval[0] = mid
            else:
                ch = (ch << 1) | 0
                lat_interval[1] = mid

        is_even = not is_even
        bits += 1

        if bits == 5:
            geohash.append(BASE32[ch])
            bits = 0
            ch = 0

    return "".join(geohash)


def geohash_decode(geohash_str: str) -> Tuple[float, float, float, float]:
    """
    Decodes a geohash string into (lat, lon, lat_error, lon_error).
    """
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    is_even = True

    for c in geohash_str.lower():
        if c not in BASE32_MAP:
            raise ValueError(f"Invalid character '{c}' in geohash")
        cd = BASE32_MAP[c]
        for mask in [16, 8, 4, 2, 1]:
            bit = (cd & mask) != 0
            if is_even:
                mid = (lon_interval[0] + lon_interval[1]) / 2.0
                if bit:
                    lon_interval[0] = mid
                else:
                    lon_interval[1] = mid
            else:
                mid = (lat_interval[0] + lat_interval[1]) / 2.0
                if bit:
                    lat_interval[0] = mid
                else:
                    lat_interval[1] = mid
            is_even = not is_even

    lat = (lat_interval[0] + lat_interval[1]) / 2.0
    lon = (lon_interval[0] + lon_interval[1]) / 2.0
    lat_err = (lat_interval[1] - lat_interval[0]) / 2.0
    lon_err = (lon_interval[1] - lon_interval[0]) / 2.0

    return lat, lon, lat_err, lon_err


# -------------------------------------------------------------
# 2. 2D Spatial QuadTree Implementation
# -------------------------------------------------------------

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two GPS points on Earth in km."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class GeoPoint:
    def __init__(self, lat: float, lon: float, data: Any = None):
        self.lat = lat
        self.lon = lon
        self.data = data


class BoundingBox:
    def __init__(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float):
        self.min_lat = min_lat
        self.min_lon = min_lon
        self.max_lat = max_lat
        self.max_lon = max_lon

    def contains(self, point: GeoPoint) -> bool:
        return (
            self.min_lat <= point.lat <= self.max_lat
            and self.min_lon <= point.lon <= self.max_lon
        )

    def intersects(self, other: "BoundingBox") -> bool:
        return not (
            other.max_lat < self.min_lat
            or other.min_lat > self.max_lat
            or other.max_lon < self.min_lon
            or other.min_lon > self.max_lon
        )


class QuadTreeNode:
    def __init__(self, boundary: BoundingBox, capacity: int = 4):
        self.boundary = boundary
        self.capacity = capacity
        self.points: List[GeoPoint] = []
        self.is_divided = False

        self.nw: Optional["QuadTreeNode"] = None
        self.ne: Optional["QuadTreeNode"] = None
        self.sw: Optional["QuadTreeNode"] = None
        self.se: Optional["QuadTreeNode"] = None

    def subdivide(self) -> None:
        mid_lat = (self.boundary.min_lat + self.boundary.max_lat) / 2.0
        mid_lon = (self.boundary.min_lon + self.boundary.max_lon) / 2.0

        self.nw = QuadTreeNode(BoundingBox(mid_lat, self.boundary.min_lon, self.boundary.max_lat, mid_lon), self.capacity)
        self.ne = QuadTreeNode(BoundingBox(mid_lat, mid_lon, self.boundary.max_lat, self.boundary.max_lon), self.capacity)
        self.sw = QuadTreeNode(BoundingBox(self.boundary.min_lat, self.boundary.min_lon, mid_lat, mid_lon), self.capacity)
        self.se = QuadTreeNode(BoundingBox(self.boundary.min_lat, mid_lon, mid_lat, self.boundary.max_lon), self.capacity)
        self.is_divided = True

    def insert(self, point: GeoPoint) -> bool:
        if not self.boundary.contains(point):
            return False

        if len(self.points) < self.capacity and not self.is_divided:
            self.points.append(point)
            return True

        if not self.is_divided:
            self.subdivide()
            # Re-insert existing points into children
            existing = self.points
            self.points = []
            for p in existing:
                self._insert_children(p)

        return self._insert_children(point)

    def _insert_children(self, point: GeoPoint) -> bool:
        return (
            self.nw.insert(point)
            or self.ne.insert(point)
            or self.sw.insert(point)
            or self.se.insert(point)
        )

    def query_range(self, search_box: BoundingBox, found: List[GeoPoint]) -> None:
        if not self.boundary.intersects(search_box):
            return

        for p in self.points:
            if search_box.contains(p):
                found.append(p)

        if self.is_divided:
            self.nw.query_range(search_box, found)
            self.ne.query_range(search_box, found)
            self.sw.query_range(search_box, found)
            self.se.query_range(search_box, found)


class QuadTreeIndex:
    """
    In-memory 2D QuadTree spatial index.
    """

    def __init__(self, root_boundary: Optional[BoundingBox] = None, capacity: int = 4):
        if root_boundary is None:
            # Whole world boundary
            root_boundary = BoundingBox(-90.0, -180.0, 90.0, 180.0)
        self.root = QuadTreeNode(root_boundary, capacity)

    def insert(self, lat: float, lon: float, data: Any = None) -> bool:
        return self.root.insert(GeoPoint(lat, lon, data))

    def query_radius(self, center_lat: float, center_lon: float, radius_km: float) -> List[Tuple[GeoPoint, float]]:
        """
        Finds all points within radius_km of (center_lat, center_lon).
        Uses BoundingBox pre-filtering + Haversine distance verification.
        """
        # 1 degree latitude ≈ 111 km
        lat_delta = radius_km / 111.0
        # 1 degree longitude ≈ 111 * cos(lat) km
        lon_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)) + 1e-9)

        search_box = BoundingBox(
            center_lat - lat_delta,
            center_lon - lon_delta,
            center_lat + lat_delta,
            center_lon + lon_delta,
        )

        candidates: List[GeoPoint] = []
        self.root.query_range(search_box, candidates)

        results = []
        for p in candidates:
            dist = haversine_distance_km(center_lat, center_lon, p.lat, p.lon)
            if dist <= radius_km:
                results.append((p, dist))

        # Sort by distance
        results.sort(key=lambda x: x[1])
        return results
