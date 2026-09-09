"""
Data Enricher v4 — Fixed for soccer.
Soccer scores are dicts with 'value' key, not strings like baseball.
Soccer team detail lacks avgPointsFor, so we calculate from game-by-game data.
"""
import logging
from typing import List, Dict, Optional
from .espn_client import ESPNClient
from .mlb_client import MLBClient
from .models import Match, Team
import config

logger = logging.getLogger(__name__)


class DataEnricher:
    def __init__(self, espn: ESPNClient, mlb: Optional[MLBClient] = None):
        self.espn = espn
        self.mlb = mlb
        self._team_cache: Dict[str, Dict] = {}
        
    def enrich_matches(self, matches: List[Match]) -> List[Match]:
        if not matches:
            return matches
        enriched = 0
        for match in matches:
            sport_key = f"{match.sport}/{match.league}"
            for team in [match.home_team, match.away_team]:
                if team.id in self._team_cache:
                    self._apply_cached(team)
                    enriched += 1
                    continue
                try:
                    self._enrich_team(team, sport_key)
                    enriched += 1
                except Exception as e:
                    logger.debug(f"Could not enrich {team.name}: {e}")
        logger.info(f"Enriched {enriched} teams across {len(matches)} matches")
        return matches
    
    def _enrich_team(self, team: Team, sport_key: str):
        # STEP 1: Game-by-game scores from schedule
        schedule_data = self._get_schedule_data(team, sport_key)
        if schedule_data:
            team.recent_form = schedule_data['form']
            team.goals_scored_last_n = schedule_data['scored']
            team.goals_conceded_last_n = schedule_data['conceded']
        
        # STEP 2: Season stats from team detail
        detail = self._get_team_detail(team, sport_key)
        if detail:
            team.overall_record = detail.get('overall_record', (0, 0, 0))
            team.home_record = detail.get('home_record', (0, 0, 0))
            team.away_record = detail.get('away_record', (0, 0, 0))
        
        # STEP 3: Calculate Elo from whatever data we have
        # Priority: team detail win% > calculated from record > calculated from form
        if detail and detail.get('elo_rating'):
            team.elo_rating = detail['elo_rating']
        elif team.overall_record[0] + team.overall_record[1] + team.overall_record[2] > 5:
            w, l, d = team.overall_record
            total = w + l + d
            win_pct = (w + d * 0.33) / total
            team.elo_rating = max(1200, min(1800, 1500 + (win_pct - 0.45) * 600))
        elif team.recent_form:
            wins = sum(1 for r in team.recent_form if r == 'W')
            draws = sum(1 for r in team.recent_form if r == 'D')
            total = len(team.recent_form)
            win_pct = (wins + draws * 0.33) / total
            team.elo_rating = max(1250, min(1750, 1500 + (win_pct - 0.45) * 500))
        
        # STEP 4: If no game-by-game scores, use season averages from detail
        if not team.goals_scored_last_n and detail:
            avg_s = detail.get('avg_scored', 0)
            avg_c = detail.get('avg_conceded', 0)
            if avg_s > 0:
                n = min(detail.get('games_played', 10), config.FORM_GAMES)
                team.goals_scored_last_n = [avg_s] * max(n, 5)
                team.goals_conceded_last_n = [avg_c] * max(n, 5)
        
        # Cache
        self._team_cache[team.id] = {
            'elo_rating': team.elo_rating,
            'goals_scored_last_n': team.goals_scored_last_n,
            'goals_conceded_last_n': team.goals_conceded_last_n,
            'overall_record': team.overall_record,
            'home_record': team.home_record,
            'away_record': team.away_record,
            'recent_form': team.recent_form,
        }
    
    def _get_schedule_data(self, team: Team, sport_key: str) -> Optional[Dict]:
        url = f"{sport_key}/teams/{team.id}/schedule"
        data = self.espn._get(url)
        if not data or 'events' not in data:
            return None
        
        form, scored, conceded = [], [], []
        
        for ev in reversed(data['events']):
            if len(form) >= config.FORM_GAMES:
                break
            comps = ev.get('competitions', [])
            if not comps:
                continue
            comp = comps[0]
            status = comp.get('status', {}).get('type', {})
            if status.get('state') != 'post' and not status.get('completed', False):
                continue
            competitors = comp.get('competitors', [])
            if len(competitors) != 2:
                continue
            
            try:
                my_comp = None
                opp_comp = None
                for c in competitors:
                    if str(c.get('id', '')) == str(team.id):
                        my_comp = c
                    else:
                        opp_comp = c
                if not my_comp or not opp_comp:
                    continue
                
                my_score = self._parse_score(my_comp.get('score', 0))
                opp_score = self._parse_score(opp_comp.get('score', 0))
                if my_score is None or opp_score is None:
                    continue
                
                scored.append(my_score)
                conceded.append(opp_score)
                if my_score > opp_score:
                    form.append('W')
                elif my_score < opp_score:
                    form.append('L')
                else:
                    form.append('D')
            except Exception:
                continue
        
        return {'form': form, 'scored': scored, 'conceded': conceded} if form else None
    
    def _parse_score(self, score_val) -> Optional[int]:
        """Handle ALL ESPN score formats:
        - Baseball: string "5" or int 5
        - Soccer: dict {'value': 2.0, 'displayValue': '2', ...}
        """
        if score_val is None:
            return None
        if isinstance(score_val, dict):
            # Soccer format: {'value': 2.0, 'displayValue': '2', ...}
            if 'value' in score_val:
                return int(float(score_val['value']))
            if 'displayValue' in score_val:
                return int(score_val['displayValue'])
            return None
        if isinstance(score_val, (int, float)):
            return int(score_val)
        if isinstance(score_val, str):
            try:
                return int(score_val)
            except ValueError:
                return None
        return None
    
    def _get_team_detail(self, team: Team, sport_key: str) -> Optional[Dict]:
        url = f"{sport_key}/teams/{team.id}"
        data = self.espn._get(url)
        if not data or 'team' not in data:
            return None
        
        team_data = data['team']
        result = {}
        record = team_data.get('record', {})
        
        for item in record.get('items', []):
            stats = {s['name']: s['value'] for s in item.get('stats', [])}
            item_type = item.get('type', '')
            
            if item_type == 'total':
                wins = int(stats.get('wins', 0))
                losses = int(stats.get('losses', 0))
                draws = int(stats.get('ties', 0))
                result['overall_record'] = (wins, losses, draws)
                result['games_played'] = int(stats.get('gamesPlayed', wins + losses + draws))
                
                # These exist for baseball but NOT soccer
                avg_f = stats.get('avgPointsFor', 0)
                avg_a = stats.get('avgPointsAgainst', 0)
                if avg_f:
                    result['avg_scored'] = avg_f
                    result['avg_conceded'] = avg_a
                
                win_pct = stats.get('winPercent', 0)
                if win_pct and (wins + losses + draws) > 10:
                    result['elo_rating'] = max(1200, min(1800, 1500 + (win_pct - 0.5) * 600))
                    
            elif item_type == 'home':
                result['home_record'] = (int(stats.get('wins', 0)), int(stats.get('losses', 0)), int(stats.get('ties', 0)))
            elif item_type == 'road':
                result['away_record'] = (int(stats.get('wins', 0)), int(stats.get('losses', 0)), int(stats.get('ties', 0)))
        
        return result if result else None
    
    def _apply_cached(self, team: Team):
        cached = self._team_cache[team.id]
        for key in ['elo_rating', 'goals_scored_last_n', 'goals_conceded_last_n',
                     'overall_record', 'home_record', 'away_record', 'recent_form']:
            val = cached.get(key)
            if val is not None:
                setattr(team, key, val)
