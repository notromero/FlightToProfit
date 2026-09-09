import requests
import logging
from typing import List, Dict, Any, Optional
import config

logger = logging.getLogger(__name__)

class OddsClient:
    def __init__(self):
        self.api_key = config.ODDS_API_KEY
        self.base_url = config.ODDS_API_BASE
        self.session = requests.Session()
        self.session.timeout = 15
        self._credits_remaining: int = 500

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("ODDS_API_KEY is not set. Odds data is unavailable.")
            return None
            
        if params is None:
            params = {}
        params['apiKey'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            
            # Track remaining credits
            remaining = response.headers.get('x-requests-remaining')
            if remaining is not None:
                self._credits_remaining = int(remaining)
                
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Error fetching from Odds API ({url}): {e}")
            return None

    def get_odds(self, sport_key: str, regions: str = 'us,eu', markets: str = 'h2h,totals') -> List[Dict[str, Any]]:
        params = {'regions': regions, 'markets': markets}
        data = self._get(f"sports/{sport_key}/odds", params)
        return data if data else []

    def get_best_odds(self, sport_key: str) -> Dict[str, Dict[str, float]]:
        events = self.get_odds(sport_key)
        best_odds = {}
        
        for event in events:
            match_id = event['id']
            home_team = event['home_team']
            away_team = event['away_team']
            
            match_odds = {'home': 0.0, 'draw': 0.0, 'away': 0.0}
            
            for bookmaker in event.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market.get('outcomes', []):
                            name = outcome['name']
                            price = outcome['price']
                            
                            if name == home_team:
                                match_odds['home'] = max(match_odds['home'], price)
                            elif name == away_team:
                                match_odds['away'] = max(match_odds['away'], price)
                            elif name.lower() == 'draw':
                                match_odds['draw'] = max(match_odds['draw'], price)
                                
            best_odds[match_id] = match_odds
            
        return best_odds

    def implied_probability(self, decimal_odds: float) -> float:
        if decimal_odds <= 0:
            return 0.0
        return 1.0 / decimal_odds

    def get_available_sports(self) -> List[Dict[str, Any]]:
        data = self._get("sports")
        return data if data else []
