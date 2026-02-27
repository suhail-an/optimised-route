"""
US city coordinates - Centralized data source.
Loads from city_coordinates.json (39,889 cities from 3 sources).
Sources: us_cities.sql, US.txt (GeoNames), uscities.csv
"""
import subprocess
import json
import urllib.parse
import os

# Load centralized data from JSON file
_data_file = os.path.join(os.path.dirname(__file__), 'city_coordinates.json')
with open(_data_file, 'r') as f:
    _city_data = json.load(f)

# Convert to tuple format for compatibility
US_CITIES = {k: tuple(v) for k, v in _city_data.items()}

# In-memory cache for API-geocoded cities (fallback)
_geocode_cache = {}


def get_city_coords(city: str, state: str, use_api_fallback: bool = False) -> tuple:
    """Get coordinates for a city/state combination.
    
    First checks the centralized database (39,889 cities).
    Optionally falls back to Nominatim API for unknown cities.
    """
    key = f"{city.upper().strip()}, {state.upper().strip()}"
    
    # Check centralized database
    if key in US_CITIES:
        return US_CITIES[key]
    
    # Check API cache
    if key in _geocode_cache:
        return _geocode_cache[key]
    
    # Optionally use API fallback
    if use_api_fallback:
        coords = _geocode_via_api(city, state)
        if coords:
            _geocode_cache[key] = coords
            return coords
    
    return None


def _geocode_via_api(city: str, state: str) -> tuple:
    """Geocode via Nominatim API (fallback for unknown cities)."""
    query = urllib.parse.quote(f"{city}, {state}, USA")
    url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1&countrycodes=us"
    
    try:
        result = subprocess.run(
            ["curl", "-s", "-k", "-A", "FuelRouteOptimizer/1.0", url],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        pass
    
    return None
