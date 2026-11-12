"""
Poisson Model v4 — Pure Python edition. No scipy, no numpy.
Clean sheets, win to nil, handicaps, team totals, multiple O/U lines.
Weather-adjusted expected goals.
"""
import math
import logging
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)

LEAGUE_AVG = {
    'soccer': {'scored': 1.35, 'conceded': 1.35},
    'baseball': {'scored': 4.5, 'conceded': 4.5},
    'basketball': {'scored': 112, 'conceded': 112},
}


def _mean(values):
    """Pure Python mean — drop-in for np.mean on lists."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _poisson_pmf(k, lam):
    """P(X=k) for Poisson(lam). Pure Python, no scipy."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


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
        """Regression to mean for small samples."""
        avg = self._get_league_avg(sport)
        league_att = avg['scored']
        league_def = avg['conceded']

        if not team.goals_scored_last_n or not team.goals_conceded_last_n:
            return league_att, league_def

        n = len(team.goals_scored_last_n)
        actual_att = _mean(team.goals_scored_last_n)
        actual_def = _mean(team.goals_conceded_last_n)

        weight = min(0.9, 0.1 + (n * 0.08))

        blended_att = (weight * actual_att) + ((1 - weight) * league_att)
        blended_def = (weight * actual_def) + ((1 - weight) * league_def)

        if sport.lower() in ('soccer', 'football', 'mls'):
            blended_att = max(0.6, blended_att)
            blended_def = max(0.4, blended_def)

        return blended_att, blended_def

    def predict_score(self, home_attack: float, home_defense: float,
                      away_attack: float, away_defense: float,
                      weather_adj: float = 1.0) -> Dict[str, float]:
        """Expected goals with optional weather adjustment."""
        home_expected = (home_attack + away_defense) / 2.0 * 1.05
        away_expected = (away_attack + home_defense) / 2.0

        # Apply weather
        home_expected *= weather_adj
        away_expected *= weather_adj

        home_expected = max(0.5, min(home_expected, 5.0))
        away_expected = max(0.4, min(away_expected, 5.0))

        return {'home_expected': home_expected, 'away_expected': away_expected}

    def score_probability(self, home_goals: int, away_goals: int,
                          home_expected: float, away_expected: float) -> float:
        return _poisson_pmf(home_goals, home_expected) * _poisson_pmf(away_goals, away_expected)

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
        max_g = 15 if line < 6 else 20
        for h in range(max_g):
            for a in range(max_g):
                if (h + a) <= line:
                    under_prob += self.score_probability(h, a, home_expected, away_expected)
        return {'over': 1.0 - under_prob, 'under': under_prob}

    def multi_over_under(self, home_expected: float, away_expected: float,
                         lines: list) -> Dict[str, Dict[str, float]]:
        """Calculate O/U for multiple lines at once."""
        results = {}
        for line in lines:
            ou = self.over_under_probability(home_expected, away_expected, line)
            results[line] = ou
        return results

    def btts_probability(self, home_expected: float, away_expected: float) -> Dict[str, float]:
        home_scores = 1.0 - _poisson_pmf(0, home_expected)
        away_scores = 1.0 - _poisson_pmf(0, away_expected)
        btts_yes = home_scores * away_scores
        return {'btts_yes': btts_yes, 'btts_no': 1.0 - btts_yes}

    def clean_sheet_probability(self, opponent_expected: float) -> float:
        """P(opponent scores 0) = P(clean sheet for this team)."""
        return _poisson_pmf(0, opponent_expected)

    def win_to_nil_probability(self, home_expected: float, away_expected: float,
                                side: str = 'home') -> float:
        """P(side wins AND opponent scores 0)."""
        if side == 'home':
            opp_zero = _poisson_pmf(0, away_expected)
            # P(home scores >= 1) * P(away scores 0)
            home_scores = 1.0 - _poisson_pmf(0, home_expected)
            return home_scores * opp_zero
        else:
            opp_zero = _poisson_pmf(0, home_expected)
            away_scores = 1.0 - _poisson_pmf(0, away_expected)
            return away_scores * opp_zero

    def handicap_probability(self, home_expected: float, away_expected: float,
                              handicap: float = -1.5, side: str = 'home') -> float:
        """P(side wins by more than |handicap|)."""
        prob = 0.0
        max_g = 10
        for h in range(max_g):
            for a in range(max_g):
                p = self.score_probability(h, a, home_expected, away_expected)
                if side == 'home':
                    margin = h - a
                else:
                    margin = a - h
                # handicap -1.5 means team needs to win by 2+
                if margin + handicap > 0:
                    prob += p
        return prob

    def team_total_probability(self, team_expected: float, line: float = 0.5,
                                over: bool = True) -> float:
        """P(team scores over/under X)."""
        under = 0.0
        for g in range(int(line) + 1):
            if g <= line:
                under += _poisson_pmf(g, team_expected)
        if over:
            return 1.0 - under
        return under

    def score_range_probability(self, home_expected: float, away_expected: float,
                                 total_min: float, total_max: float) -> float:
        """P(total goals between min and max)."""
        prob = 0.0
        for h in range(15):
            for a in range(15):
                total = h + a
                if total_min <= total <= total_max:
                    prob += self.score_probability(h, a, home_expected, away_expected)
        return prob
