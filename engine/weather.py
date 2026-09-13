"""
Weather Engine — Open-Meteo API (FREE, no key).
Fetches real weather for game venues, calculates impact on scoring.
"""
import logging
import requests
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# GPS coordinates for major venues
VENUE_COORDS = {
    # MLB Stadiums
    'yankee stadium': (40.8296, -73.9262), 'citi field': (40.7571, -73.8458),
    'fenway park': (42.3467, -71.0972), 'citizens bank park': (39.9061, -75.1665),
    'nationals park': (38.8730, -77.0074), 'oriole park': (39.2838, -76.6218),
    'camden yards': (39.2838, -76.6218), 'tropicana field': (27.7682, -82.6534),
    'loanDepot park': (25.7781, -80.2196), 'truist park': (33.8907, -84.4677),
    'pnc park': (40.4469, -80.0057), 'progressive field': (41.4962, -81.6852),
    'comerica park': (42.3390, -83.0485), 'wrigley field': (41.9484, -87.6553),
    'guaranteed rate field': (41.8300, -87.6339), 'american family field': (43.0280, -87.9712),
    'busch stadium': (38.6226, -90.1928), 'target field': (44.9817, -93.2776),
    'kauffman stadium': (39.0517, -94.4803), 'globe life field': (32.7472, -97.0844),
    'minute maid park': (29.7572, -95.3554), 'coors field': (39.7559, -104.9942),
    'chase field': (33.4453, -112.0667), 'dodger stadium': (34.0739, -118.2400),
    'angel stadium': (33.8003, -117.8827), 'petco park': (32.7076, -117.1570),
    'oracle park': (37.7786, -122.3893), 'oakland coliseum': (37.7516, -122.2005),
    't-mobile park': (47.5914, -122.3325), 'rogers centre': (43.6414, -79.3894),
    # Soccer
    'old trafford': (53.4631, -2.2913), 'anfield': (53.4308, -2.9608),
    'emirates stadium': (51.5549, -0.1084), 'stamford bridge': (51.4817, -0.1910),
    'etihad stadium': (53.4831, -2.2004), 'santiago bernabeu': (40.4530, -3.6883),
    'camp nou': (41.3809, 2.1228), 'allianz arena': (48.2188, 11.6247),
    'san siro': (45.4781, 9.1240), 'parc des princes': (48.8414, 2.2530),
    'ataturk olympic': (41.0747, 28.7650), 'turk telekom': (41.1033, 28.9947),
}

# Default: approximate center of USA
DEFAULT_COORDS = (39.8283, -98.5795)


class WeatherEngine:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10
        self._cache = {}

    def _find_coords(self, venue: str) -> tuple:
        if not venue:
            return DEFAULT_COORDS
        v = venue.lower().strip()
        for name, coords in VENUE_COORDS.items():
            if name in v or v in name:
                return coords
        # Fuzzy: check if any word matches
        words = v.split()
        for name, coords in VENUE_COORDS.items():
            for w in words:
                if len(w) > 4 and w in name:
                    return coords
        return DEFAULT_COORDS

    def get_game_weather(self, venue: str, game_time_iso: str) -> dict:
        """Fetch weather from Open-Meteo for venue at game time."""
        defaults = {
            'temperature_f': 72, 'wind_mph': 5, 'precipitation_pct': 0,
            'humidity_pct': 50, 'description': 'Unknown'
        }
        
        try:
            lat, lon = self._find_coords(venue)
            
            cache_key = f"{lat:.2f},{lon:.2f},{game_time_iso[:10]}"
            if cache_key in self._cache:
                return self._match_hour(self._cache[cache_key], game_time_iso)

            resp = self.session.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat, 'longitude': lon,
                'hourly': 'temperature_2m,precipitation_probability,windspeed_10m,relativehumidity_2m',
                'temperature_unit': 'fahrenheit', 'windspeed_unit': 'mph',
                'timezone': 'auto', 'forecast_days': 3
            })
            resp.raise_for_status()
            data = resp.json()
            self._cache[cache_key] = data
            return self._match_hour(data, game_time_iso)
        except Exception as e:
            logger.warning(f"Weather fetch failed for {venue}: {e}")
            return defaults

    def _match_hour(self, data: dict, game_time_iso: str) -> dict:
        defaults = {
            'temperature_f': 72, 'wind_mph': 5, 'precipitation_pct': 0,
            'humidity_pct': 50, 'description': 'Unknown'
        }
        try:
            hourly = data.get('hourly', {})
            times = hourly.get('time', [])
            if not times:
                return defaults

            # Find closest hour
            game_hour = game_time_iso[:13]  # "2026-09-12T22"
            best_idx = 0
            for i, t in enumerate(times):
                if t[:13] == game_hour:
                    best_idx = i
                    break
                if t[:10] == game_time_iso[:10]:
                    best_idx = i

            temp = hourly.get('temperature_2m', [72])[best_idx]
            wind = hourly.get('windspeed_10m', [5])[best_idx]
            precip = hourly.get('precipitation_probability', [0])[best_idx]
            humid = hourly.get('relativehumidity_2m', [50])[best_idx]

            # Build description
            parts = []
            if temp: parts.append(f"{temp:.0f}°F")
            if wind: parts.append(f"Wind {wind:.0f}mph")
            if precip and precip > 30: parts.append(f"Rain {precip}%")
            desc = ', '.join(parts) if parts else 'Clear'

            return {
                'temperature_f': temp or 72,
                'wind_mph': wind or 5,
                'precipitation_pct': precip or 0,
                'humidity_pct': humid or 50,
                'description': desc
            }
        except Exception:
            return defaults

    def calculate_weather_impact(self, weather: dict, sport: str) -> dict:
        """Calculate how weather affects scoring."""
        total_adj = 1.0
        home_boost = 0.0
        flags = []
        
        temp = weather.get('temperature_f', 72)
        wind = weather.get('wind_mph', 5)
        precip = weather.get('precipitation_pct', 0)
        humid = weather.get('humidity_pct', 50)
        is_baseball = sport.lower() in ('baseball', 'mlb')

        # Rain
        if precip > 50:
            total_adj *= 0.88
            home_boost += 0.03
            flags.append(f'🌧️ Rain {precip}% — favors UNDER')
        elif precip > 30:
            total_adj *= 0.95
            flags.append(f'🌦️ Rain possible {precip}%')

        # Wind
        if wind > 15:
            if is_baseball:
                total_adj *= 1.08  # wind carries balls out
                flags.append(f'💨 Wind {wind:.0f}mph — favors OVER')
            else:
                total_adj *= 0.92
                flags.append(f'💨 Wind {wind:.0f}mph — favors UNDER')
        elif wind > 10:
            if is_baseball:
                total_adj *= 1.03

        # Cold
        if temp < 50:
            total_adj *= 0.93
            flags.append(f'🥶 Cold {temp:.0f}°F')
        elif temp < 60:
            total_adj *= 0.97

        # Heat
        if temp > 95:
            total_adj *= 0.95
            flags.append(f'🔥 Heat {temp:.0f}°F — fatigue factor')

        # Humidity (baseball specific)
        if is_baseball and humid > 80:
            total_adj *= 0.97
            flags.append(f'💧 Humid {humid}%')

        # Summary
        if not flags:
            summary = '☀️ Perfect conditions'
        else:
            summary = ' | '.join(flags)

        return {
            'total_adjustment': total_adj,
            'home_boost': home_boost,
            'flags': flags,
            'summary': summary
        }
