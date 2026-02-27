"""
Fuel data module for loading and querying fuel station data.
"""
import pandas as pd
import subprocess
import json
from typing import List, Dict, Optional, Tuple, Set
from us_cities import get_city_coords

# State bounding boxes (approximate lat/lon ranges)
# Used to quickly determine which states a route passes through
STATE_BOUNDS = {
    'AL': (30.2, 35.0, -88.5, -84.9), 'AZ': (31.3, 37.0, -114.8, -109.0),
    'AR': (33.0, 36.5, -94.6, -89.6), 'CA': (32.5, 42.0, -124.4, -114.1),
    'CO': (37.0, 41.0, -109.1, -102.0), 'CT': (41.0, 42.1, -73.7, -71.8),
    'DE': (38.5, 39.8, -75.8, -75.0), 'FL': (24.5, 31.0, -87.6, -80.0),
    'GA': (30.4, 35.0, -85.6, -80.8), 'ID': (42.0, 49.0, -117.2, -111.0),
    'IL': (37.0, 42.5, -91.5, -87.5), 'IN': (37.8, 41.8, -88.1, -84.8),
    'IA': (40.4, 43.5, -96.6, -90.1), 'KS': (37.0, 40.0, -102.1, -94.6),
    'KY': (36.5, 39.1, -89.6, -82.0), 'LA': (29.0, 33.0, -94.0, -89.0),
    'ME': (43.1, 47.5, -71.1, -66.9), 'MD': (37.9, 39.7, -79.5, -75.0),
    'MA': (41.2, 42.9, -73.5, -69.9), 'MI': (41.7, 48.3, -90.4, -82.4),
    'MN': (43.5, 49.4, -97.2, -89.5), 'MS': (30.2, 35.0, -91.7, -88.1),
    'MO': (36.0, 40.6, -95.8, -89.1), 'MT': (44.4, 49.0, -116.0, -104.0),
    'NE': (40.0, 43.0, -104.1, -95.3), 'NV': (35.0, 42.0, -120.0, -114.0),
    'NH': (42.7, 45.3, -72.6, -70.7), 'NJ': (38.9, 41.4, -75.6, -73.9),
    'NM': (31.3, 37.0, -109.0, -103.0), 'NY': (40.5, 45.0, -79.8, -71.9),
    'NC': (33.8, 36.6, -84.3, -75.5), 'ND': (45.9, 49.0, -104.0, -96.6),
    'OH': (38.4, 42.0, -84.8, -80.5), 'OK': (33.6, 37.0, -103.0, -94.4),
    'OR': (42.0, 46.3, -124.6, -116.5), 'PA': (39.7, 42.3, -80.5, -74.7),
    'RI': (41.1, 42.0, -71.9, -71.1), 'SC': (32.0, 35.2, -83.4, -78.5),
    'SD': (42.5, 46.0, -104.1, -96.4), 'TN': (35.0, 36.7, -90.3, -81.6),
    'TX': (25.8, 36.5, -106.6, -93.5), 'UT': (37.0, 42.0, -114.1, -109.0),
    'VT': (42.7, 45.0, -73.4, -71.5), 'VA': (36.5, 39.5, -83.7, -75.2),
    'WA': (45.5, 49.0, -124.8, -116.9), 'WV': (37.2, 40.6, -82.6, -77.7),
    'WI': (42.5, 47.1, -92.9, -86.8), 'WY': (41.0, 45.0, -111.1, -104.1),
}


def get_states_from_route_geometry(route_geometry: Dict) -> Set[str]:
    """Determine which states a route passes through using bounding boxes."""
    if not route_geometry or 'coordinates' not in route_geometry:
        return set()

    coords = route_geometry['coordinates']
    states = set()

    # Sample points along the route (every ~50 points)
    step = max(1, len(coords) // 50)
    sample_points = coords[::step]

    for lon, lat in sample_points:
        for state, (min_lat, max_lat, min_lon, max_lon) in STATE_BOUNDS.items():
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                states.add(state)

    return states


class FuelDataManager:
    """Manages fuel station data from CSV file."""

    def __init__(self, csv_path: str = "fuel.csv"):
        self.df = self._load_data(csv_path)
        self._stations_cache = None
        self._route_stations_cache = {}  # Cache for route-specific stations

    def _load_data(self, csv_path: str) -> pd.DataFrame:
        """Load and clean fuel data from CSV."""
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        us_states = [
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
        ]
        df = df[df['State'].isin(us_states)]
        df = df.groupby(['OPIS Truckstop ID', 'Truckstop Name', 'Address', 'City', 'State']).agg({
            'Retail Price': 'min',
            'Rack ID': 'first'
        }).reset_index()
        return df

    def get_stations_with_coords(self) -> List[Dict]:
        """Get all stations with coordinates (local lookup only, fast)."""
        if self._stations_cache is not None:
            return self._stations_cache

        stations = []
        for _, row in self.df.iterrows():
            coords = get_city_coords(row['City'], row['State'], use_api_fallback=False)
            if coords:
                stations.append({
                    'id': row['OPIS Truckstop ID'],
                    'name': row['Truckstop Name'],
                    'address': row['Address'],
                    'city': row['City'],
                    'state': row['State'],
                    'price': float(row['Retail Price']),
                    'lat': coords[0],
                    'lon': coords[1]
                })

        self._stations_cache = stations
        return stations

    def get_stations_near_route(self, route_geometry: Dict) -> List[Dict]:
        """Get stations near a route with API fallback for geocoding.

        1. Determines states along the route (fast, no API)
        2. Filters stations to those states
        3. Uses local lookup first, then API fallback for unknown cities
        """
        states = get_states_from_route_geometry(route_geometry)
        if not states:
            return self.get_stations_with_coords()

        # Create a cache key from sorted states
        cache_key = tuple(sorted(states))
        if cache_key in self._route_stations_cache:
            return self._route_stations_cache[cache_key]

        # Filter to stations in states along the route
        filtered_df = self.df[self.df['State'].isin(states)]

        # Pre-geocode unique cities (API fallback limited to 10 cities max for speed)
        unique_cities = filtered_df[['City', 'State']].drop_duplicates()
        city_coords_cache = {}
        api_calls = 0

        # Import US_CITIES once for efficiency
        from us_cities import US_CITIES

        for _, row in unique_cities.iterrows():
            city, state = row['City'].strip(), row['State'].strip()
            key = f"{city.upper()}, {state.upper()}"

            # Check if we need API (not in local dict)
            needs_api = key not in US_CITIES

            # Only use API fallback if under limit (10 max for ~10 seconds of API calls)
            use_api = needs_api and api_calls < 10
            coords = get_city_coords(city, state, use_api_fallback=use_api)
            city_coords_cache[key] = coords

            if needs_api and coords:
                api_calls += 1

        # Build stations list using cached coordinates
        stations = []
        for _, row in filtered_df.iterrows():
            key = f"{row['City'].strip().upper()}, {row['State'].strip().upper()}"
            coords = city_coords_cache.get(key)
            if coords:
                stations.append({
                    'id': row['OPIS Truckstop ID'],
                    'name': row['Truckstop Name'],
                    'address': row['Address'],
                    'city': row['City'],
                    'state': row['State'],
                    'price': float(row['Retail Price']),
                    'lat': coords[0],
                    'lon': coords[1]
                })

        self._route_stations_cache[cache_key] = stations
        return stations

    def get_all_stations(self) -> List[Dict]:
        """Get all stations as dictionaries."""
        return self.df.to_dict('records')

    def get_stations_by_state(self, state: str) -> List[Dict]:
        """Get stations in a specific state."""
        filtered = self.df[self.df['State'] == state.upper()]
        return filtered.to_dict('records')

    def get_cheapest_stations(self, n: int = 10) -> List[Dict]:
        """Get the n cheapest stations."""
        sorted_df = self.df.nsmallest(n, 'Retail Price')
        return sorted_df.to_dict('records')


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """Geocode any address to lat/lon using Nominatim via curl (handles SSL better)."""
    import urllib.parse

    query = urllib.parse.quote(f"{address}, USA")
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1&countrycodes=us"

    try:
        result = subprocess.run(
            ["curl", "-s", "-k", "-A", "FuelRouteOptimizer/1.0", url],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception as e:
        print(f"Geocoding error: {e}")

    return None

