"""
Poisson Model v2 — Fixed regression to mean.
Small sample sizes get blended with league average.
No more fake 98% Under 2.5 on every game.
"""
import logging
import numpy as np
from scipy.stats import poisson
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)

# Real league averages (goals per team per game) from historical data
LEAGUE_AVG = {
    'soccer': {'scored': 1.35, 'conceded': 1.35},  # ~2.7 total goals per game
    'baseball': {'scored': 4.5, 'conceded': 4.5},   # ~9.0 total runs per game
    'basketball': {'scored': 112, 'conceded': 112},
}

class PoissonModel:
    def __init__(self):
        pass

    def _get_league_avg(self, sport: str = 'soccer') -> dict:
        sport = sport.lower()
        if sport in ('mlb', 'baseball'):
            return LEAGUE_AVG['baseball']
        elif sport in ('nba', 'basketball'):
            return LEAGUE_AVG['basketball']
        return LEAGUE_AVG['soccer']

    def calculate_attack_defense(self, team: Any, sport: str = 'soccer') -> Tuple[float, float]:
        """
        Derive attacking and defensive strengths.
        KEY FIX: Regression to mean for small samples.
        With 1 game: 80% league avg + 20% actual
        With 5 games: 50% league avg + 50% actual
        With 10+ games: 90% actual + 10% league avg
        """
        avg = self._get_league_avg(sport)
        league_att = avg['scored']
        league_def = avg['conceded']
        
        if not team.goals_scored_last_n or not team.goals_conceded_last_n:
            return league_att, league_def
        
        n = len(team.goals_scored_last_n)
        actual_att = float(np.mean(team.goals_scored_last_n))
        actual_def = float(np.mean(team.goals_conceded_last_n))
        
        # Regression weight: more games = trust actual data more
        # 1 game = 0.2 weight, 3 games = 0.4, 5 games = 0.6, 10+ = 0.9
        weight = min(0.9, 0.1 + (n * 0.08))
        
        blended_att = (weight * actual_att) + ((1 - weight) * league_att)
        blended_def = (weight * actual_def) + ((1 - weight) * league_def)
        
        # Floor: never go below 0.5 for soccer (teams always have SOME chance)
        if sport.lower() in ('soccer', 'football', 'mls'):
            blended_att = max(0.6, blended_att)
            blended_def = max(0.4, blended_def)
        
        return blended_att, blended_def

    def predict_score(self, home_attack: float, home_defense: float, 
                      away_attack: float, away_defense: float, 
                      league_avg_goals: float = 1.35) -> Dict[str, float]:
        """Calculate expected goals — home team gets ~10% boost."""
        # Simple and honest: attack vs opponent defense
        home_expected = (home_attack + away_defense) / 2.0 * 1.05  # slight home boost
        away_expected = (away_attack + home_defense) / 2.0
        
        # Sanity clamp
        home_expected = max(0.5, min(home_expected, 4.0))
        away_expected = max(0.4, min(away_expected, 4.0))
        
        return {'home_expected': home_expected, 'away_expected': away_expected}

    def score_probability(self, home_goals: int, away_goals: int, 
                          home_expected: float, away_expected: float) -> float:
        return float(poisson.pmf(home_goals, home_expected) * poisson.pmf(away_goals, away_expected))

    def match_outcome_probabilities(self, home_expected: float, away_expected: float, 
                                    max_goals: int = 8) -> Dict[str, float]:
        home_win = draw = away_win = 0.0
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob = self.score_probability(h, a, home_expected, away_expected)
                if h > a: home_win += prob
                elif h < a: away_win += prob
                else: draw += prob
        total = home_win + draw + away_win
        return {'home_win': home_win/total, 'draw': draw/total, 'away_win': away_win/total}

    def over_under_probability(self, home_expected: float, away_expected: float, 
                               line: float = 2.5) -> Dict[str, float]:
        under_prob = 0.0
        for h in range(15):
            for a in range(15):
                if (h + a) <= line:
                    under_prob += self.score_probability(h, a, home_expected, away_expected)
        return {'over': 1.0 - under_prob, 'under': under_prob}

    def btts_probability(self, home_expected: float, away_expected: float) -> Dict[str, float]:
        home_scores = 1.0 - poisson.pmf(0, home_expected)
        away_scores = 1.0 - poisson.pmf(0, away_expected)
        btts_yes = float(home_scores * away_scores)
        return {'btts_yes': btts_yes, 'btts_no': 1.0 - btts_yes}
