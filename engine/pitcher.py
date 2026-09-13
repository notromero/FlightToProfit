"""
Pitcher Analysis — MLB Stats API.
Rates starting pitchers, calculates matchup edges, adjusts run expectations.
"""
import logging
import requests
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MLB_API = 'https://statsapi.mlb.com/api/v1'


class PitcherAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 12
        self._cache = {}

    def get_starter_stats(self, pitcher_id: int, season: int = 2026) -> dict:
        """Fetch pitcher season stats."""
        cache_key = f"stats_{pitcher_id}_{season}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            url = f"{MLB_API}/people/{pitcher_id}"
            resp = self.session.get(url, params={
                'hydrate': f'stats(group=[pitching],type=[season],season={season})'
            })
            resp.raise_for_status()
            data = resp.json()
            
            person = data.get('people', [{}])[0]
            stats_list = person.get('stats', [])
            if not stats_list:
                return {}
            
            splits = stats_list[0].get('splits', [])
            if not splits:
                return {}
            
            s = splits[0].get('stat', {})
            result = {
                'name': person.get('fullName', 'Unknown'),
                'era': float(s.get('era', 4.50)),
                'whip': float(s.get('whip', 1.30)),
                'strikeouts': int(s.get('strikeOuts', 0)),
                'walks': int(s.get('baseOnBalls', 0)),
                'innings_pitched': float(s.get('inningsPitched', '0').replace('.', '')),
                'wins': int(s.get('wins', 0)),
                'losses': int(s.get('losses', 0)),
                'games_started': int(s.get('gamesStarted', 0)),
                'home_runs': int(s.get('homeRuns', 0)),
                'hits': int(s.get('hits', 0)),
            }
            
            # Calculate K/9 and BB/9
            ip = result['innings_pitched']
            if ip > 0:
                result['k9'] = round(result['strikeouts'] / ip * 9, 2)
                result['bb9'] = round(result['walks'] / ip * 9, 2)
                result['hr9'] = round(result['home_runs'] / ip * 9, 2)
                result['k_bb'] = round(result['strikeouts'] / max(1, result['walks']), 2)
            else:
                result['k9'] = 0
                result['bb9'] = 0
                result['hr9'] = 0
                result['k_bb'] = 0
            
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch pitcher stats {pitcher_id}: {e}")
            return {}

    def get_recent_starts(self, pitcher_id: int, season: int = 2026, num: int = 3) -> list:
        """Get last N starts with game log."""
        try:
            url = f"{MLB_API}/people/{pitcher_id}/stats"
            resp = self.session.get(url, params={
                'stats': 'gameLog', 'group': 'pitching', 'season': season
            })
            resp.raise_for_status()
            data = resp.json()
            
            stats = data.get('stats', [])
            if not stats:
                return []
            
            splits = stats[0].get('splits', [])
            # Filter to starts only (GS > 0 or IP > 3)
            starts = []
            for s in reversed(splits):
                stat = s.get('stat', {})
                ip = float(stat.get('inningsPitched', '0').replace('.1', '.33').replace('.2', '.67'))
                if ip >= 3.0:  # Likely a start
                    starts.append({
                        'date': s.get('date', ''),
                        'opponent': s.get('opponent', {}).get('name', ''),
                        'ip': ip,
                        'runs': int(stat.get('runs', 0)),
                        'er': int(stat.get('earnedRuns', 0)),
                        'k': int(stat.get('strikeOuts', 0)),
                        'bb': int(stat.get('baseOnBalls', 0)),
                        'hits': int(stat.get('hits', 0)),
                    })
                if len(starts) >= num:
                    break
            return starts
        except Exception as e:
            logger.debug(f"Failed to fetch game log {pitcher_id}: {e}")
            return []

    def rate_pitcher(self, stats: dict) -> dict:
        """Rate pitcher 0-100 based on stats."""
        if not stats:
            return {'rating': 50, 'grade': 'UNKNOWN', 'era': 0, 'whip': 0, 'k9': 0}
        
        era = stats.get('era', 4.50)
        whip = stats.get('whip', 1.30)
        k_bb = stats.get('k_bb', 2.0)
        ip = stats.get('innings_pitched', 0)
        
        # ERA base score
        if era < 2.50: score = 95
        elif era < 3.00: score = 85
        elif era < 3.50: score = 72
        elif era < 4.00: score = 60
        elif era < 4.50: score = 48
        elif era < 5.00: score = 35
        else: score = 20
        
        # WHIP adjustment
        if whip < 1.00: score += 8
        elif whip < 1.15: score += 4
        elif whip > 1.40: score -= 6
        elif whip > 1.30: score -= 3
        
        # K/BB adjustment
        if k_bb > 4.0: score += 6
        elif k_bb > 3.0: score += 3
        elif k_bb < 1.5: score -= 5
        elif k_bb < 2.0: score -= 3
        
        # Workload bonus
        if ip > 150: score += 3
        elif ip > 100: score += 1
        
        score = max(10, min(99, score))
        
        # Grade
        if score >= 85: grade = 'ACE'
        elif score >= 70: grade = 'SOLID'
        elif score >= 50: grade = 'AVERAGE'
        elif score >= 35: grade = 'BELOW_AVG'
        else: grade = 'BAD'
        
        return {
            'rating': score,
            'grade': grade,
            'era': era,
            'whip': whip,
            'k9': stats.get('k9', 0),
            'name': stats.get('name', 'Unknown')
        }

    def get_matchup_edge(self, home_rating: dict, away_rating: dict) -> dict:
        """Compare two pitcher ratings for matchup edge."""
        hr = home_rating.get('rating', 50)
        ar = away_rating.get('rating', 50)
        gap = abs(hr - ar)
        
        if gap < 8:
            edge_team = 'neutral'
            edge_word = 'Even matchup'
        elif hr > ar:
            edge_team = 'home'
            edge_word = 'Home pitching edge'
        else:
            edge_team = 'away'
            edge_word = 'Away pitching edge'
        
        # Build summary
        hn = home_rating.get('name', '?')
        an = away_rating.get('name', '?')
        he = home_rating.get('era', 0)
        ae = away_rating.get('era', 0)
        
        if gap >= 20:
            intensity = 'HUGE'
        elif gap >= 12:
            intensity = 'Strong'
        elif gap >= 8:
            intensity = 'Slight'
        else:
            intensity = ''
        
        summary = f"{hn} ({he:.2f} ERA) vs {an} ({ae:.2f} ERA)"
        if intensity:
            summary += f" — {intensity} {edge_word.lower()}"
        
        return {
            'edge_team': edge_team,
            'edge_size': gap,
            'summary': summary,
            'home_rating': hr,
            'away_rating': ar
        }

    def adjust_expected_runs(self, base_xr: float, pitcher_rating: int) -> float:
        """Adjust expected runs based on pitcher quality."""
        if pitcher_rating >= 85:
            return base_xr * 0.78
        elif pitcher_rating >= 70:
            return base_xr * 0.90
        elif pitcher_rating >= 50:
            return base_xr * 1.0
        elif pitcher_rating >= 35:
            return base_xr * 1.12
        else:
            return base_xr * 1.25

    def get_todays_starters(self, date: str = None) -> dict:
        """Get all probable pitchers for today's games."""
        try:
            params = {'sportId': 1, 'hydrate': 'probablePitcher(note)'}
            if date:
                params['date'] = date
            resp = self.session.get(f"{MLB_API}/schedule", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            starters = {}
            for date_obj in data.get('dates', []):
                for game in date_obj.get('games', []):
                    game_pk = game.get('gamePk')
                    teams = game.get('teams', {})
                    entry = {}
                    for side in ('home', 'away'):
                        pitcher = teams.get(side, {}).get('probablePitcher', {})
                        if pitcher:
                            pid = pitcher.get('id')
                            entry[f'{side}_pitcher_id'] = pid
                            entry[f'{side}_pitcher_name'] = pitcher.get('fullName', '?')
                    if entry:
                        starters[str(game_pk)] = entry
            return starters
        except Exception as e:
            logger.warning(f"Failed to fetch starters: {e}")
            return {}
