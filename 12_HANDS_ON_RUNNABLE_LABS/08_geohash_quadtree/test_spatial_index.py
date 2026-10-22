"""
Unit tests for Geohash and QuadTree Spatial Indexing.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from spatial_index import (
    BoundingBox,
    QuadTreeIndex,
    geohash_decode,
    geohash_encode,
    haversine_distance_km,
)


class TestSpatialIndex(unittest.TestCase):

    def test_geohash_encoding_and_decoding(self):
        # Coordinates for Statue of Liberty, NYC: 40.6892, -74.0445
        lat = 40.6892
        lon = -74.0445
        precision = 8

        gh = geohash_encode(lat, lon, precision)
        self.assertEqual(len(gh), precision)
        self.assertTrue(gh.startswith("dr5r"))  # NYC geohash prefix

        # Decode back
        d_lat, d_lon, lat_err, lon_err = geohash_decode(gh)
        self.assertAlmostEqual(lat, d_lat, delta=lat_err)
        self.assertAlmostEqual(lon, d_lon, delta=lon_err)

    def test_geohash_spatial_proximity(self):
        # Two locations in Manhattan, NYC
        times_square = (40.7580, -73.9855)
        empire_state = (40.7484, -73.9857)
        # Location in London, UK
        big_ben = (51.5007, -0.1246)

        gh_ts = geohash_encode(*times_square, precision=6)
        gh_es = geohash_encode(*empire_state, precision=6)
        gh_bb = geohash_encode(*big_ben, precision=6)

        # Close locations share longer prefix
        self.assertEqual(gh_ts[:4], gh_es[:4])  # Both start with "dr5r"
        # London location has completely different prefix
        self.assertNotEqual(gh_ts[:2], gh_bb[:2])

    def test_quadtree_radius_query(self):
        # Regional box around San Francisco: lat [37.0, 38.0], lon [-123.0, -122.0]
        qt = QuadTreeIndex(BoundingBox(37.0, -123.0, 38.0, -122.0), capacity=2)

        # Insert 4 drivers around SF Downtown (37.7749, -122.4194)
        qt.insert(37.7749, -122.4194, "Driver_Downtown")
        qt.insert(37.7755, -122.4180, "Driver_Near_1km")    # ~0.15 km away
        qt.insert(37.7900, -122.4000, "Driver_Medium_3km")  # ~2.4 km away
        qt.insert(37.3382, -121.8863, "Driver_San_Jose")    # ~70 km away

        # Query radius of 2.0 km around SF Downtown
        results_2km = qt.query_radius(37.7749, -122.4194, radius_km=2.0)
        drivers_found = [p.data for p, dist in results_2km]

        self.assertIn("Driver_Downtown", drivers_found)
        self.assertIn("Driver_Near_1km", drivers_found)
        self.assertNotIn("Driver_Medium_3km", drivers_found)
        self.assertNotIn("Driver_San_Jose", drivers_found)

        # Query radius of 5.0 km
        results_5km = qt.query_radius(37.7749, -122.4194, radius_km=5.0)
        drivers_found_5km = [p.data for p, dist in results_5km]
        self.assertIn("Driver_Medium_3km", drivers_found_5km)
        self.assertNotIn("Driver_San_Jose", drivers_found_5km)


if __name__ == "__main__":
    unittest.main()
