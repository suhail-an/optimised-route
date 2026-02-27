"""
Routing module using multiple routing APIs.
Primary: GraphHopper (fastest, 500 req/day free)
Fallback: OSRM (Open Source Routing Machine)
"""
import requests
from typing import List, Dict, Optional, Tuple
import math
import subprocess
import json as json_lib

# GraphHopper API - fastest option
GRAPHHOPPER_API_KEY = "ceb75a1b-5b30-41c4-a215-0293e9f42954"
GRAPHHOPPER_URL = "https://graphhopper.com/api/1/route"

# OSRM servers as fallback
OSRM_SERVERS = [
    "https://router.project-osrm.org",
    "http://router.project-osrm.org",
]


def _curl_request(url: str, headers: dict = None) -> Optional[Dict]:
    """Make HTTP request using curl (handles SSL better on macOS)."""
    try:
        cmd = ["curl", "-s", "-k"]
        if headers:
            for k, v in headers.items():
                cmd.extend(["-H", f"{k}: {v}"])
        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and result.stdout:
            return json_lib.loads(result.stdout)
    except Exception as e:
        print(f"Curl error: {e}")
    return None


def _try_graphhopper(start: Tuple[float, float], end: Tuple[float, float]) -> Optional[Dict]:
    """Try GraphHopper API (fastest option)."""
    url = (f"{GRAPHHOPPER_URL}?point={start[0]},{start[1]}&point={end[0]},{end[1]}"
           f"&vehicle=car&locale=en&calc_points=true&points_encoded=false"
           f"&key={GRAPHHOPPER_API_KEY}")

    data = _curl_request(url)

    if data and "paths" in data and data["paths"]:
        path = data["paths"][0]

        # Convert points to GeoJSON LineString format
        points = path.get("points", {})
        geometry = {
            "type": "LineString",
            "coordinates": points.get("coordinates", [])
        }

        return {
            "distance_meters": path.get("distance", 0),
            "distance_miles": path.get("distance", 0) / 1609.34,
            "duration_seconds": path.get("time", 0) / 1000,  # GraphHopper returns ms
            "geometry": geometry,
            "legs": []
        }

    # Check for error message
    if data and "message" in data:
        print(f"GraphHopper error: {data['message']}")

    return None


def _make_osrm_request(url: str, params: dict) -> Optional[Dict]:
    """Make request to OSRM, with curl fallback for SSL issues."""
    try:
        response = requests.get(url, params=params, timeout=30)
        return response.json()
    except Exception:
        pass

    # Fallback to curl
    try:
        full_url = url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        return _curl_request(full_url)
    except Exception as e:
        print(f"OSRM error: {e}")
    return None


def get_route(start: Tuple[float, float], end: Tuple[float, float]) -> Optional[Dict]:
    """
    Get a route between two points.
    Tries GraphHopper first (fastest), falls back to OSRM.

    Args:
        start: (latitude, longitude) of start point
        end: (latitude, longitude) of end point

    Returns:
        Route data including distance, duration, and geometry
    """
    # Try GraphHopper first (fastest)
    print("Trying GraphHopper...")
    result = _try_graphhopper(start, end)
    if result:
        print("GraphHopper succeeded!")
        return result

    # Fallback to OSRM
    print("GraphHopper failed, trying OSRM...")
    start_str = f"{start[1]},{start[0]}"
    end_str = f"{end[1]},{end[0]}"

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true"
    }

    for server in OSRM_SERVERS:
        url = f"{server}/route/v1/driving/{start_str};{end_str}"
        data = _make_osrm_request(url, params)

        if data and data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            print(f"OSRM succeeded ({server})")
            return {
                "distance_meters": route["distance"],
                "distance_miles": route["distance"] / 1609.34,
                "duration_seconds": route["duration"],
                "geometry": route["geometry"],
                "legs": route.get("legs", [])
            }

    print("All routing servers failed")
    return None


def get_route_with_waypoints(points: List[Tuple[float, float]]) -> Optional[Dict]:
    """
    Get a route through multiple waypoints using OSRM.

    Args:
        points: List of (latitude, longitude) tuples

    Returns:
        Route data including distance, duration, and geometry
    """
    if len(points) < 2:
        return None

    # OSRM uses lon,lat format
    coords_str = ";".join([f"{p[1]},{p[0]}" for p in points])

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true"
    }

    for server in OSRM_SERVERS:
        url = f"{server}/route/v1/driving/{coords_str}"
        data = _make_osrm_request(url, params)

        if data and data.get("code") == "Ok" and data.get("routes"):
            route = data["routes"][0]
            return {
                "distance_meters": route["distance"],
                "distance_miles": route["distance"] / 1609.34,
                "duration_seconds": route["duration"],
                "geometry": route["geometry"],
                "legs": route.get("legs", [])
            }

    return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points in miles.
    """
    R = 3959  # Earth's radius in miles
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def interpolate_point_on_route(geometry: Dict, distance_miles: float) -> Optional[Tuple[float, float]]:
    """
    Find a point on the route at approximately the given distance from start.
    
    Args:
        geometry: GeoJSON geometry of the route
        distance_miles: Distance from start in miles
    
    Returns:
        (latitude, longitude) of the interpolated point
    """
    if geometry.get("type") != "LineString":
        return None
    
    coords = geometry["coordinates"]  # [[lon, lat], ...]
    cumulative_distance = 0
    
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        segment_distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        if cumulative_distance + segment_distance >= distance_miles:
            # Interpolate within this segment
            remaining = distance_miles - cumulative_distance
            ratio = remaining / segment_distance if segment_distance > 0 else 0
            
            interp_lat = lat1 + ratio * (lat2 - lat1)
            interp_lon = lon1 + ratio * (lon2 - lon1)
            return (interp_lat, interp_lon)
        
        cumulative_distance += segment_distance
    
    # Return last point if distance exceeds route length
    return (coords[-1][1], coords[-1][0])

