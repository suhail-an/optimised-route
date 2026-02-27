# Fuel Route Optimizer API

A high-performance REST API that calculates optimal fuel stops along driving routes within the USA. The system finds the cheapest fuel stations along your route while ensuring you never run out of gas.

## Features

- 🗺️ **Cross-country routing** - Calculate routes between any two US locations
- ⛽ **Smart fuel optimization** - Finds the cheapest fuel stations within your vehicle's range
- 🗄️ **Extensive database** - 39,889 US cities with instant coordinate lookup
- 📍 **6,800+ fuel stations** - Real pricing data for truck stops across the USA
- 🌐 **Interactive maps** - Visualize routes with Leaflet-powered maps
- ⚡ **Fast performance** - ~15-25 second response time for cross-country routes

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### API Usage

**Calculate optimal fuel stops (JSON):**
```bash
curl -X POST "http://localhost:8000/route" \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "finish": "Los Angeles, CA"}'
```

**View interactive map (Browser):**
```
http://localhost:8000/route/map?start=New%20York,%20NY&finish=Los%20Angeles,%20CA
```

## API Endpoints

### `POST /route`
Calculate optimal fuel stops for a route.

**Request Body:**
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA",
  "max_range_miles": 500,
  "mpg": 10
}
```

**Response:**
```json
{
  "start_location": "New York, NY",
  "end_location": "Los Angeles, CA",
  "total_distance_miles": 2776.39,
  "total_duration_hours": 40.35,
  "fuel_stops": [
    {
      "name": "SHEETZ #774",
      "city": "New Concord",
      "state": "OH",
      "price": 3.059,
      "distance_from_start": 465.1
    }
  ],
  "total_gallons": 277.64,
  "total_fuel_cost": 807.82,
  "average_price_per_gallon": 2.91
}
```

### `GET /route/map`
Returns an interactive HTML map showing the route and fuel stops.

**Parameters:**
- `start` (required): Starting location
- `finish` (required): Destination

### `GET /stations`
List fuel stations with optional filtering.

**Parameters:**
- `state`: Filter by state code (e.g., "TX", "CA")
- `limit`: Maximum stations to return (default: 100)

## Project Structure

```
├── app.py                  # FastAPI application & endpoints
├── routing.py              # GraphHopper/OSRM routing integration
├── fuel_optimizer.py       # Fuel stop optimization algorithm
├── fuel_data.py            # Fuel station data manager
├── us_cities.py            # City coordinate lookups
├── map_generator.py        # Leaflet map HTML generation
├── city_coordinates.json   # 39,889 US city coordinates
├── fuel.csv                # Fuel station pricing data
└── requirements.txt        # Python dependencies
```

## Configuration

### Vehicle Settings

Default vehicle parameters (can be overridden per request):
- **max_range_miles**: 500 miles (vehicle range on full tank)
- **mpg**: 10 miles per gallon (fuel efficiency)

### Routing Engine

The system uses **GraphHopper** as the primary routing engine with OSRM fallback:

```python
# routing.py
GRAPHHOPPER_API_KEY = "your-api-key-here"
```

Get a free GraphHopper API key at: https://www.graphhopper.com/dashboard/#/register
- Free tier: 500 requests/day
- Response time: ~10-20 seconds for cross-country routes

## Algorithm

### Fuel Optimization Strategy

The optimizer uses a **greedy look-ahead algorithm**:

1. Start with a full tank at origin
2. At each decision point, look ahead within remaining range
3. Find all reachable fuel stations
4. Among stations in the latter half of range, pick the cheapest
5. Refuel and repeat until destination is reachable

### Performance Optimizations

- **Route downsampling**: For routes with >500 points, samples every Nth point
- **State-based filtering**: Only considers stations in states along the route
- **Coordinate caching**: City coordinates loaded once at startup
- **Station caching**: Geocoded stations cached per route

## Data Sources

### City Coordinates (`city_coordinates.json`)
- **39,889 unique US cities**
- Sources: us_cities.sql, GeoNames US.txt, uscities.csv
- Format: `{"CITY, STATE": [latitude, longitude]}`

### Fuel Stations (`fuel.csv`)
- **6,800+ truck stops** with current pricing
- Fields: Truckstop ID, Name, Address, City, State, Retail Price

