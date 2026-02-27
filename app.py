"""
Fuel Route Optimizer API

An API that calculates optimal fuel stops along a route within the USA.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

from fuel_data import FuelDataManager, geocode_address
from routing import get_route, get_route_with_waypoints, haversine_distance
from fuel_optimizer import FuelOptimizer
from map_generator import generate_map_html

app = FastAPI(
    title="Fuel Route Optimizer API",
    description="Find optimal fuel stops along your route in the USA",
    version="1.0.0"
)

# Initialize data manager and optimizer
fuel_manager = FuelDataManager("fuel.csv")
fuel_optimizer = FuelOptimizer(max_range_miles=500, mpg=10)

# Cache for geocoded stations
_stations_cache = None


class RouteRequest(BaseModel):
    start: str  # Starting location (city, state or address)
    finish: str  # Destination (city, state or address)
    max_range_miles: Optional[float] = 500
    mpg: Optional[float] = 10


class FuelStop(BaseModel):
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lon: float
    distance_from_start: float


class RouteResponse(BaseModel):
    start_location: str
    end_location: str
    start_coords: List[float]
    end_coords: List[float]
    total_distance_miles: float
    total_duration_hours: float
    fuel_stops: List[Dict]
    total_gallons: float
    total_fuel_cost: float
    average_price_per_gallon: float
    map_url: str


def get_cached_stations():
    """Get geocoded stations - instant with local lookup."""
    global _stations_cache
    if _stations_cache is None:
        _stations_cache = fuel_manager.get_stations_with_coords()
    return _stations_cache


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "Fuel Route Optimizer API",
        "docs": "/docs",
        "endpoints": {
            "/route": "POST - Calculate optimal fuel stops for a route",
            "/route/map": "GET - Get route map with fuel stops",
            "/stations": "GET - List all fuel stations"
        }
    }


@app.post("/route", response_model=RouteResponse)
async def calculate_route(request: RouteRequest):
    """
    Calculate optimal fuel stops for a route.

    - **start**: Starting location (e.g., "Los Angeles, CA" or "123 Main St, Denver, CO")
    - **finish**: Destination location
    - **max_range_miles**: Vehicle's maximum range on a full tank (default: 500)
    - **mpg**: Vehicle's fuel efficiency in miles per gallon (default: 10)
    """
    # Geocode start and finish
    start_coords = geocode_address(request.start)
    if not start_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode start location: {request.start}")

    end_coords = geocode_address(request.finish)
    if not end_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode finish location: {request.finish}")

    # Get route
    route = get_route(start_coords, end_coords)
    if not route:
        raise HTTPException(status_code=500, detail="Could not calculate route")

    # Configure optimizer with custom settings
    optimizer = FuelOptimizer(
        max_range_miles=request.max_range_miles or 500,
        mpg=request.mpg or 10
    )

    # Get stations near the route (filters by states, uses API fallback for unknown cities)
    stations = fuel_manager.get_stations_near_route(route["geometry"])

    # Find optimal fuel stops
    result = optimizer.find_optimal_fuel_stops(
        route_geometry=route["geometry"],
        total_distance_miles=route["distance_miles"],
        fuel_stations=stations,
        start_coords=start_coords,
        end_coords=end_coords
    )

    # Build response
    return {
        "start_location": request.start,
        "end_location": request.finish,
        "start_coords": list(start_coords),
        "end_coords": list(end_coords),
        "total_distance_miles": round(route["distance_miles"], 2),
        "total_duration_hours": round(route["duration_seconds"] / 3600, 2),
        "fuel_stops": result.get("optimal_stops", []),
        "total_gallons": result.get("total_gallons", 0),
        "total_fuel_cost": result.get("total_fuel_cost", 0),
        "average_price_per_gallon": result.get("average_price_per_gallon", 0),
        "map_url": f"/route/map?start={request.start}&finish={request.finish}"
    }


@app.get("/stations")
async def get_stations(
    state: Optional[str] = Query(None, description="Filter by state code (e.g., TX, CA)"),
    limit: int = Query(100, description="Maximum number of stations to return")
):
    """Get list of fuel stations (raw data without coordinates)."""
    if state:
        stations = fuel_manager.get_stations_by_state(state.upper())
    else:
        stations = fuel_manager.get_all_stations()

    return {
        "count": len(stations[:limit]),
        "stations": stations[:limit]
    }


@app.get("/route/map", response_class=HTMLResponse)
async def get_route_map(
    start: str = Query(..., description="Starting location"),
    finish: str = Query(..., description="Destination")
):
    """
    Get an interactive map showing the route and optimal fuel stops.
    """
    # Geocode locations
    start_coords = geocode_address(start)
    if not start_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode: {start}")

    end_coords = geocode_address(finish)
    if not end_coords:
        raise HTTPException(status_code=400, detail=f"Could not geocode: {finish}")

    # Get route
    route = get_route(start_coords, end_coords)
    if not route:
        raise HTTPException(status_code=500, detail="Could not calculate route")

    # Get stations near the route and optimize
    stations = fuel_manager.get_stations_near_route(route["geometry"])
    result = fuel_optimizer.find_optimal_fuel_stops(
        route_geometry=route["geometry"],
        total_distance_miles=route["distance_miles"],
        fuel_stations=stations,
        start_coords=start_coords,
        end_coords=end_coords
    )

    fuel_stops = result.get("optimal_stops", [])

    # Generate map HTML
    html = generate_map_html(
        start=start,
        finish=finish,
        start_coords=start_coords,
        end_coords=end_coords,
        route_geometry=route["geometry"],
        fuel_stops=fuel_stops,
        total_distance=route["distance_miles"],
        total_duration=route["duration_seconds"] / 3600,
        total_gallons=result.get("total_gallons", 0),
        total_cost=result.get("total_fuel_cost", 0)
    )

    return HTMLResponse(content=html)

