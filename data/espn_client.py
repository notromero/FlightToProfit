import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .models import Match, Team
import config

logger = logging.getLogger(__name__)

class ESPNClient:
    def __init__(self):
        self.base_url = config.ESPN_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        })
        self.session.timeout = 15
        self._cache = {}
        self._cache_ttl = 30 * 60  # 30 minutes

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        # A simple cache key
        cache_key = f"{endpoint}_{params}"
        if cache_key in self._cache:
            timestamp, data = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data

        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            self._cache[cache_key] = (time.time(), data)
            return data
        except requests.RequestException as e:
            logger.warning(f"Error fetching from ESPN API ({url}): {e}")
            return None

    def get_scoreboard(self, sport_key: str, date: Optional[str] = None) -> List[Match]:
        params = {}
        if date:
            params['dates'] = date
        
        data = self._get(f"{sport_key}/scoreboard", params)
        if not data or 'events' not in data:
            return []

        matches = []
        for event in data['events']:
            try:
                event_id = event['id']
                # basic checking
                if 'competitions' not in event or not event['competitions']:
                    continue
                
                comp = event['competitions'][0]
                competitors = comp.get('competitors', [])
                if len(competitors) != 2:
                    continue

                home_comp = next((c for c in competitors if c['homeAway'] == 'home'), None)
                away_comp = next((c for c in competitors if c['homeAway'] == 'away'), None)

                if not home_comp or not away_comp:
                    continue
                
                home_team = Team(
                    id=home_comp['id'],
                    name=home_comp['team']['displayName'],
                    abbreviation=home_comp['team'].get('abbreviation', ''),
                    sport=sport_key.split('/')[0],
                    league=sport_key.split('/')[1] if '/' in sport_key else sport_key
                )

                away_team = Team(
                    id=away_comp['id'],
                    name=away_comp['team']['displayName'],
                    abbreviation=away_comp['team'].get('abbreviation', ''),
                    sport=sport_key.split('/')[0],
                    league=sport_key.split('/')[1] if '/' in sport_key else sport_key
                )

                status = event['status']['type']['name']
                start_time_str = event['date']
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))

                match = Match(
                    id=event_id,
                    sport=home_team.sport,
                    league=home_team.league,
                    home_team=home_team,
                    away_team=away_team,
                    start_time=start_time,
                    status=status
                )

                if 'score' in home_comp:
                    match.home_score = int(home_comp['score'])
                if 'score' in away_comp:
                    match.away_score = int(away_comp['score'])
                
                matches.append(match)
            except Exception as e:
                logger.warning(f"Error parsing event {event.get('id', 'unknown')}: {e}")
        return matches

    def get_team_schedule(self, sport_key: str, team_id: str, season: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if season:
            params['season'] = season
            
        data = self._get(f"{sport_key}/teams/{team_id}/schedule", params)
        if not data or 'events' not in data:
            return []
            
        results = []
        for event in data['events']:
            try:
                comp = event['competitions'][0]
                status = event['status']['type']['state']
                if status != 'post':
                    continue
                
                date = event['date']
                competitors = comp.get('competitors', [])
                
                my_team_comp = next((c for c in competitors if c['id'] == team_id), None)
                opp_team_comp = next((c for c in competitors if c['id'] != team_id), None)
                
                if not my_team_comp or not opp_team_comp:
                    continue
                
                my_score = int(my_team_comp.get('score', 0))
                opp_score = int(opp_team_comp.get('score', 0))
                
                result = 'D'
                if my_score > opp_score:
                    result = 'W'
                elif my_score < opp_score:
                    result = 'L'
                    
                results.append({
                    'date': date,
                    'opponent': opp_team_comp['team']['displayName'],
                    'home_away': my_team_comp['homeAway'],
                    'score_for': my_score,
                    'score_against': opp_score,
                    'result': result
                })
            except Exception as e:
                logger.debug(f"Skipping event {event.get('id')} in schedule due to parse error: {e}")
                
        return results

    def get_standings(self, sport_key: str) -> Dict[str, Dict[str, Any]]:
        data = self._get(f"{sport_key}/standings")
        if not data or 'children' not in data:
            return {}
            
        standings = {}
        try:
            for child in data['children']:
                if 'standings' in child:
                    for entry in child['standings'].get('entries', []):
                        team_id = entry['team']['id']
                        stats = {s['name']: s['value'] for s in entry['stats']}
                        standings[team_id] = {
                            'wins': stats.get('wins', 0),
                            'losses': stats.get('losses', 0),
                            'draws': stats.get('ties', 0),
                            'rank': stats.get('rank', 0)
                        }
        except Exception as e:
            logger.warning(f"Error parsing standings for {sport_key}: {e}")
            
        return standings

    def get_todays_matches(self, sports: Optional[List[str]] = None) -> List[Match]:
        """ONLY today's games in Lebanese time."""
        import pytz
        beirut = pytz.timezone('Asia/Beirut')
        now_beirut = datetime.now(beirut)
        today_date = now_beirut.date()
        
        if not sports:
            sports = list(config.SUPPORTED_SPORTS.values())
        
        # Fetch from ESPN using both UTC dates that could contain today's Lebanese games
        matches = []
        utc_today = datetime.utcnow().strftime('%Y%m%d')
        utc_tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y%m%d')
        
        for sport in sports:
            matches.extend(self.get_scoreboard(sport, utc_today))
            matches.extend(self.get_scoreboard(sport, utc_tomorrow))
        
        # Filter: only keep games where Lebanese date matches today
        filtered = []
        seen_ids = set()
        for m in matches:
            if m.id in seen_ids:
                continue
            seen_ids.add(m.id)
            if m.start_time:
                m_beirut = m.start_time.astimezone(beirut) if m.start_time.tzinfo else beirut.localize(m.start_time)
                if m_beirut.date() == today_date:
                    filtered.append(m)
        
        filtered.sort(key=lambda m: m.start_time)
        return filtered

    def get_tomorrows_matches(self, sports: Optional[List[str]] = None) -> List[Match]:
        """ONLY tomorrow's games in Lebanese time."""
        import pytz
        beirut = pytz.timezone('Asia/Beirut')
        now_beirut = datetime.now(beirut)
        tomorrow_date = (now_beirut + timedelta(days=1)).date()
        
        if not sports:
            sports = list(config.SUPPORTED_SPORTS.values())
        
        # Fetch from ESPN using UTC dates that could contain tomorrow's Lebanese games
        matches = []
        utc_today = datetime.utcnow().strftime('%Y%m%d')
        utc_tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y%m%d')
        utc_day_after = (datetime.utcnow() + timedelta(days=2)).strftime('%Y%m%d')
        
        for sport in sports:
            matches.extend(self.get_scoreboard(sport, utc_tomorrow))
            matches.extend(self.get_scoreboard(sport, utc_day_after))
        
        # Filter: only keep games where Lebanese date matches tomorrow
        filtered = []
        seen_ids = set()
        for m in matches:
            if m.id in seen_ids:
                continue
            seen_ids.add(m.id)
            if m.start_time:
                m_beirut = m.start_time.astimezone(beirut) if m.start_time.tzinfo else beirut.localize(m.start_time)
                if m_beirut.date() == tomorrow_date:
                    filtered.append(m)
        
        filtered.sort(key=lambda m: m.start_time)
        return filtered

    def get_team_recent_results(self, sport_key: str, team_id: str, n: int = 10) -> List[Dict[str, Any]]:
        schedule = self.get_team_schedule(sport_key, team_id)
        return schedule[-n:] if schedule else []
