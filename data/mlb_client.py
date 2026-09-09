import requests
import logging
from typing import List, Dict, Any, Optional
import config

logger = logging.getLogger(__name__)

class MLBClient:
    def __init__(self):
        self.base_url = config.MLB_API_BASE
        self.session = requests.Session()
        self.session.timeout = 15

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Error fetching from MLB API ({url}): {e}")
            return None

    def get_schedule(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {'sportId': 1, 'hydrate': 'probablePitcher'}
        if date:
            params['date'] = date
            
        data = self._get("schedule", params)
        if not data or 'dates' not in data or not data['dates']:
            return []
            
        return data['dates'][0].get('games', [])

    def get_team_stats(self, team_id: int, season: int = 2026) -> Dict[str, Any]:
        params = {'stats': 'season', 'group': 'hitting,pitching', 'season': season}
        data = self._get(f"teams/{team_id}/stats", params)
        
        if not data or 'stats' not in data:
            return {}
            
        stats = {}
        for stat_group in data['stats']:
            group_name = stat_group['group']['displayName']
            splits = stat_group.get('splits', [])
            if splits:
                stats[group_name] = splits[0]['stat']
                
        return stats

    def get_probable_pitchers(self, game_pk: int) -> Dict[str, Any]:
        data = self._get(f"game/{game_pk}/feed/live")
        if not data or 'gameData' not in data:
            return {}
            
        pitchers = {}
        probable = data['gameData'].get('probablePitchers', {})
        
        for side in ['home', 'away']:
            if side in probable:
                pitcher_info = probable[side]
                pitchers[f"{side}_pitcher"] = {
                    'name': pitcher_info.get('fullName', 'Unknown'),
                    'id': pitcher_info.get('id')
                }
                
        return pitchers

    def get_head_to_head(self, team1_id: int, team2_id: int, season: int = 2026) -> List[Dict[str, Any]]:
        params = {
            'sportId': 1,
            'teamId': team1_id,
            'opponentId': team2_id,
            'season': season
        }
        data = self._get("schedule", params)
        
        if not data or 'dates' not in data:
            return []
            
        meetings = []
        for date_obj in data['dates']:
            for game in date_obj.get('games', []):
                if game['status']['statusCode'] == 'F':
                    meetings.append(game)
        return meetings

    def get_standings(self) -> Dict[str, Any]:
        params = {'leagueId': '103,104', 'season': 2026}
        data = self._get("standings", params)
        
        if not data or 'records' not in data:
            return {}
            
        standings = {}
        for record in data['records']:
            for team_rec in record.get('teamRecords', []):
                team_id = team_rec['team']['id']
                standings[team_id] = {
                    'wins': team_rec.get('wins', 0),
                    'losses': team_rec.get('losses', 0)
                }
        return standings
