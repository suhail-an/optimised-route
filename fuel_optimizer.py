"""
Fuel optimization algorithm to find optimal fuel stops along a route.
"""
from typing import List, Dict, Tuple, Optional
from routing import haversine_distance, interpolate_point_on_route
import math


class FuelOptimizer:
    """
    Optimizes fuel stops along a route based on price and vehicle range.
    """
    
    def __init__(self, max_range_miles: float = 500, mpg: float = 10):
        self.max_range = max_range_miles
        self.mpg = mpg
        self.search_radius_miles = 20  # Search for stations within this radius of route
    
    def find_optimal_fuel_stops(
        self,
        route_geometry: Dict,
        total_distance_miles: float,
        fuel_stations: List[Dict],
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float]
    ) -> Dict:
        """
        Find optimal fuel stops along a route.
        
        Args:
            route_geometry: GeoJSON geometry of the route
            total_distance_miles: Total route distance in miles
            fuel_stations: List of fuel station dicts with lat, lon, price, etc.
            start_coords: (lat, lon) of start point
            end_coords: (lat, lon) of end point
        
        Returns:
            Dict with optimal_stops, total_fuel_cost, total_gallons, etc.
        """
        # If route is within range, no fuel stop needed
        if total_distance_miles <= self.max_range:
            gallons_needed = total_distance_miles / self.mpg
            return {
                "optimal_stops": [],
                "total_gallons": gallons_needed,
                "total_fuel_cost": 0,  # Assuming tank is full at start
                "message": "Route is within vehicle range. No fuel stop needed."
            }
        
        # Find stations near the route
        route_stations = self._find_stations_near_route(
            route_geometry, fuel_stations, start_coords
        )
        
        if not route_stations:
            return {
                "optimal_stops": [],
                "total_gallons": total_distance_miles / self.mpg,
                "total_fuel_cost": 0,
                "message": "No fuel stations found near route. Please plan manually.",
                "error": True
            }
        
        # Use greedy algorithm with look-ahead for optimal stops
        optimal_stops = self._greedy_fuel_stops(
            route_stations, total_distance_miles, start_coords, end_coords
        )
        
        # Calculate total cost
        total_gallons = total_distance_miles / self.mpg
        total_cost = self._calculate_total_cost(optimal_stops, total_distance_miles)
        
        return {
            "optimal_stops": optimal_stops,
            "total_gallons": round(total_gallons, 2),
            "total_fuel_cost": round(total_cost, 2),
            "fuel_stops_count": len(optimal_stops),
            "average_price_per_gallon": round(total_cost / total_gallons, 3) if total_gallons > 0 else 0
        }
    
    def _find_stations_near_route(
        self,
        geometry: Dict,
        stations: List[Dict],
        start_coords: Tuple[float, float]
    ) -> List[Dict]:
        """Find stations near the route and calculate their distance from start."""
        route_stations = []
        coords = geometry.get("coordinates", [])

        # Downsample route for faster processing (keep every Nth point)
        # For a 2800-mile route with 10000 points, sample ~500 points
        sample_rate = max(1, len(coords) // 500)
        sampled_coords = coords[::sample_rate]

        # Pre-calculate cumulative distances for sampled points
        cumulative_distances = [0]
        for i in range(1, len(sampled_coords)):
            prev_lon, prev_lat = sampled_coords[i-1]
            lon, lat = sampled_coords[i]
            cumulative_distances.append(
                cumulative_distances[-1] + haversine_distance(prev_lat, prev_lon, lat, lon)
            )

        for station in stations:
            if 'lat' not in station or 'lon' not in station:
                continue

            slat, slon = station['lat'], station['lon']

            # Check if station is near any point on the route
            min_distance_to_route = float('inf')
            distance_along_route = 0

            for i, coord in enumerate(sampled_coords):
                lon, lat = coord
                dist_to_station = haversine_distance(lat, lon, slat, slon)

                if dist_to_station < min_distance_to_route:
                    min_distance_to_route = dist_to_station
                    distance_along_route = cumulative_distances[i]

            if min_distance_to_route <= self.search_radius_miles:
                station_with_dist = station.copy()
                station_with_dist['distance_from_start'] = distance_along_route
                station_with_dist['distance_to_route'] = min_distance_to_route
                route_stations.append(station_with_dist)

        # Sort by distance from start
        route_stations.sort(key=lambda x: x['distance_from_start'])
        return route_stations
    
    def _greedy_fuel_stops(
        self,
        stations: List[Dict],
        total_distance: float,
        start: Tuple[float, float],
        end: Tuple[float, float]
    ) -> List[Dict]:
        """
        Greedy algorithm: At each point, look ahead within remaining range
        and pick the cheapest station.
        """
        stops = []
        current_position = 0  # miles from start
        remaining_range = self.max_range  # Assume we start with a full tank
        
        while current_position + remaining_range < total_distance:
            # Find the farthest point we can reach
            max_reach = current_position + remaining_range
            
            # Find all stations we can reach
            reachable = [
                s for s in stations
                if current_position < s['distance_from_start'] <= max_reach
            ]
            
            if not reachable:
                # No reachable station - this is a problem
                # Find the nearest station ahead
                ahead = [s for s in stations if s['distance_from_start'] > current_position]
                if ahead:
                    # Take the closest one (even if out of range - edge case)
                    nearest = min(ahead, key=lambda x: x['distance_from_start'])
                    stops.append(nearest)
                    current_position = nearest['distance_from_start']
                    remaining_range = self.max_range
                else:
                    break
                continue
            
            # Among reachable stations, find the cheapest one that's far enough
            # We want to minimize cost while maximizing distance covered
            # Strategy: Look at stations in the latter half of our range and pick cheapest
            far_reachable = [s for s in reachable if s['distance_from_start'] > current_position + remaining_range * 0.5]
            
            if far_reachable:
                best = min(far_reachable, key=lambda x: x['price'])
            else:
                # All stations are close, pick the cheapest
                best = min(reachable, key=lambda x: x['price'])
            
            stops.append(best)
            current_position = best['distance_from_start']
            remaining_range = self.max_range  # Refuel to full

        return stops

    def _calculate_total_cost(self, stops: List[Dict], total_distance: float) -> float:
        """
        Calculate total fuel cost for the trip.

        Assumes we fill up at each stop for the next leg of the journey.
        """
        if not stops:
            return 0

        total_cost = 0
        total_gallons = total_distance / self.mpg

        # Distribute gallons across stops based on segment lengths
        prev_pos = 0
        for i, stop in enumerate(stops):
            # Distance from previous position to this stop
            if i == len(stops) - 1:
                # Last stop - fuel for remaining distance to destination
                next_pos = total_distance
            else:
                next_pos = stops[i + 1]['distance_from_start']

            segment_distance = next_pos - stop['distance_from_start']
            gallons_for_segment = segment_distance / self.mpg

            # Add a buffer (fill up more than needed)
            gallons_purchased = min(gallons_for_segment * 1.2, self.max_range / self.mpg)
            total_cost += gallons_purchased * stop['price']

            prev_pos = stop['distance_from_start']

        return total_cost

