"""
Map generation module using Leaflet.
"""
from typing import List, Dict, Tuple
import json


def generate_map_html(
    start: str,
    finish: str,
    start_coords: Tuple[float, float],
    end_coords: Tuple[float, float],
    route_geometry: Dict,
    fuel_stops: List[Dict],
    total_distance: float,
    total_duration: float,
    total_gallons: float,
    total_cost: float
) -> str:
    """
    Generate an HTML page with an interactive Leaflet map.
    """
    # Calculate center of map
    center_lat = (start_coords[0] + end_coords[0]) / 2
    center_lon = (start_coords[1] + end_coords[1]) / 2
    
    # Convert route geometry to Leaflet format
    route_coords = [[coord[1], coord[0]] for coord in route_geometry.get("coordinates", [])]
    
    # Prepare fuel stops data
    stops_json = json.dumps([{
        'name': s.get('name', 'Unknown'),
        'city': s.get('city', ''),
        'state': s.get('state', ''),
        'price': s.get('price', 0),
        'lat': s.get('lat', 0),
        'lon': s.get('lon', 0),
        'distance_from_start': s.get('distance_from_start', 0)
    } for s in fuel_stops])
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Fuel Route: {start} to {finish}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 70vh; width: 100%; }}
        .info-panel {{
            padding: 20px;
            background: #f5f5f5;
            border-top: 2px solid #333;
        }}
        .info-panel h2 {{ margin-top: 0; color: #333; }}
        .stats {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 15px; }}
        .stat-box {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 150px;
        }}
        .stat-box h4 {{ margin: 0 0 5px 0; color: #666; font-size: 12px; }}
        .stat-box .value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
        .fuel-stops-list {{ margin-top: 15px; }}
        .fuel-stop {{
            background: white;
            padding: 10px 15px;
            margin: 5px 0;
            border-radius: 4px;
            border-left: 4px solid #4CAF50;
        }}
        .fuel-stop .name {{ font-weight: bold; }}
        .fuel-stop .details {{ color: #666; font-size: 14px; }}
        .fuel-stop .price {{ color: #4CAF50; font-weight: bold; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-panel">
        <h2>🚗 Route: {start} → {finish}</h2>
        <div class="stats">
            <div class="stat-box">
                <h4>TOTAL DISTANCE</h4>
                <div class="value">{total_distance:.1f} mi</div>
            </div>
            <div class="stat-box">
                <h4>DRIVE TIME</h4>
                <div class="value">{total_duration:.1f} hrs</div>
            </div>
            <div class="stat-box">
                <h4>FUEL NEEDED</h4>
                <div class="value">{total_gallons:.1f} gal</div>
            </div>
            <div class="stat-box">
                <h4>TOTAL FUEL COST</h4>
                <div class="value">${total_cost:.2f}</div>
            </div>
            <div class="stat-box">
                <h4>FUEL STOPS</h4>
                <div class="value">{len(fuel_stops)}</div>
            </div>
        </div>
        <div class="fuel-stops-list" id="fuel-stops-list"></div>
    </div>

    <script>
        // Initialize map
        var map = L.map('map').setView([{center_lat}, {center_lon}], 6);
        
        // Add tile layer (OpenStreetMap)
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Route coordinates
        var routeCoords = {json.dumps(route_coords)};
        
        // Draw route
        var route = L.polyline(routeCoords, {{
            color: '#2196F3',
            weight: 5,
            opacity: 0.8
        }}).addTo(map);
        
        // Fit map to route
        map.fitBounds(route.getBounds().pad(0.1));
        
        // Start marker (green)
        var startIcon = L.divIcon({{
            className: 'custom-div-icon',
            html: '<div style="background-color:#4CAF50;width:20px;height:20px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        }});
        L.marker([{start_coords[0]}, {start_coords[1]}], {{icon: startIcon}})
            .bindPopup('<b>Start:</b> {start}')
            .addTo(map);
        
        // End marker (red)
        var endIcon = L.divIcon({{
            className: 'custom-div-icon',
            html: '<div style="background-color:#f44336;width:20px;height:20px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        }});
        L.marker([{end_coords[0]}, {end_coords[1]}], {{icon: endIcon}})
            .bindPopup('<b>Destination:</b> {finish}')
            .addTo(map);
        
        // Fuel stops
        var fuelStops = {stops_json};
        var fuelStopsList = document.getElementById('fuel-stops-list');

        if (fuelStops.length > 0) {{
            fuelStopsList.innerHTML = '<h3>⛽ Recommended Fuel Stops:</h3>';

            fuelStops.forEach(function(stop, index) {{
                // Add marker to map
                var fuelIcon = L.divIcon({{
                    className: 'custom-div-icon',
                    html: '<div style="background-color:#FF9800;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:12px;">' + (index + 1) + '</div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                }});

                L.marker([stop.lat, stop.lon], {{icon: fuelIcon}})
                    .bindPopup('<b>' + stop.name + '</b><br>' + stop.city + ', ' + stop.state + '<br>Price: <b>$' + stop.price.toFixed(3) + '/gal</b><br>Distance from start: ' + stop.distance_from_start.toFixed(1) + ' mi')
                    .addTo(map);

                // Add to list
                fuelStopsList.innerHTML += '<div class="fuel-stop">' +
                    '<span class="name">' + (index + 1) + '. ' + stop.name + '</span>' +
                    '<div class="details">' + stop.city + ', ' + stop.state + ' | ' + stop.distance_from_start.toFixed(1) + ' miles from start</div>' +
                    '<div class="price">$' + stop.price.toFixed(3) + ' per gallon</div>' +
                    '</div>';
            }});
        }} else {{
            fuelStopsList.innerHTML = '<p style="color: #4CAF50;">✓ No fuel stops needed - route is within vehicle range!</p>';
        }}
</script>
</body>
</html>'''

    return html

