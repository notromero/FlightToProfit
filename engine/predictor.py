"""
Predictor v3 — MONEY LINE FOCUSED.
Stop trying to predict Over/Under. Focus on WHO WINS.
Heavy favorites + form confirmation = 70%+ win rate.
"""
import logging
import numpy as np
from typing import List, Dict, Optional, Any
from data.models import Match, Prediction, Team
from engine.elo import EloRating
from engine.poisson import PoissonModel
from engine.form_analyzer import FormAnalyzer
from engine.h2h_analyzer import H2HAnalyzer
from engine.value_detector import ValueDetector

logger = logging.getLogger(__name__)

class Predictor:
    def __init__(self):
        self.elo = EloRating()
        self.poisson = PoissonModel()
        self.form = FormAnalyzer()
        self.h2h = H2HAnalyzer()
        self.value = ValueDetector()

    def _team_strength(self, team: Team, is_home: bool) -> float:
        """Calculate overall team strength 0-100 scale."""
        score = 50.0  # baseline
        
        # Elo contribution (biggest factor)
        elo_diff = team.elo_rating - 1500
        score += elo_diff * 0.02  # +/- 10 points for 500 elo diff
        
        # Form contribution
        if team.recent_form:
            last5 = team.recent_form[-5:]
            wins = last5.count('W')
            losses = last5.count('L')
            form_score = (wins - losses) * 3
            score += form_score
        
        # Record contribution
        w, l, d = team.overall_record
        total = w + l + d
        if total > 0:
            win_pct = w / total
            score += (win_pct - 0.5) * 20  # +/- 10 points
        
        # Home advantage
        if is_home:
            score += 5
        
        # Goal scoring/conceding
        if team.goals_scored_last_n and team.goals_conceded_last_n:
            avg_scored = np.mean(team.goals_scored_last_n)
            avg_conceded = np.mean(team.goals_conceded_last_n)
            goal_diff = avg_scored - avg_conceded
            score += goal_diff * 3
        
        return max(10, min(90, score))

    def predict_match(self, match: Match, h2h: list = None) -> Prediction:
        home = match.home_team
        away = match.away_team
        h2h = h2h or []
        
        home_strength = self._team_strength(home, is_home=True)
        away_strength = self._team_strength(away, is_home=False)
        
        strength_diff = home_strength - away_strength
        
        # Convert strength difference to win probability
        # Using logistic function: bigger diff = higher confidence
        home_win_prob = 1.0 / (1.0 + 10 ** (-strength_diff / 15.0))
        away_win_prob = 1.0 - home_win_prob
        
        # For soccer: carve out draw probability
        is_soccer = match.sport.lower() in ('soccer', 'football')
        draw_prob = 0.0
        
        if is_soccer:
            # Draw probability decreases with strength difference
            base_draw = 0.26  # ~26% of soccer games are draws
            draw_reduction = min(0.20, abs(strength_diff) * 0.015)
            draw_prob = max(0.05, base_draw - draw_reduction)
            
            # Redistribute draw prob proportionally
            total_win = home_win_prob + away_win_prob
            home_win_prob = home_win_prob / total_win * (1.0 - draw_prob)
            away_win_prob = away_win_prob / total_win * (1.0 - draw_prob)
        
        # Poisson for goal-based markets
        home_att, home_def = self.poisson.calculate_attack_defense(home, sport=match.sport)
        away_att, away_def = self.poisson.calculate_attack_defense(away, sport=match.sport)
        xg = self.poisson.predict_score(home_att, home_def, away_att, away_def)
        
        he = xg['home_expected']
        ae = xg['away_expected']
        
        ou_line = 2.5 if is_soccer else 8.5
        ou_probs = self.poisson.over_under_probability(he, ae, line=ou_line)
        btts_probs = self.poisson.btts_probability(he, ae)
        
        # Build all possible bets with probabilities
        bets = {}
        bets['HOME_WIN'] = home_win_prob
        bets['AWAY_WIN'] = away_win_prob
        
        if is_soccer:
            bets['DRAW'] = draw_prob
            bets['BTTS_YES'] = btts_probs['btts_yes']
            bets['BTTS_NO'] = btts_probs['btts_no']
            # Double Chance — protects against draws
            bets['HOME_OR_DRAW'] = home_win_prob + draw_prob
            bets['AWAY_OR_DRAW'] = away_win_prob + draw_prob
        
        bets[f'OVER_{ou_line}'] = ou_probs['over']
        bets[f'UNDER_{ou_line}'] = ou_probs['under']
        
        # Pick the BEST bet
        best_bet = max(bets, key=bets.get)
        best_prob = bets[best_bet]
        
        # Secondary bets — other high-confidence picks for same match
        # These are INDEPENDENT markets (can combine in same-game parlay)
        SECONDARY_THRESHOLD = 0.58
        secondary = []
        
        # Group by market type so we don't conflict
        market_of = {
            'HOME_WIN': 'winner', 'AWAY_WIN': 'winner', 'DRAW': 'winner',
            'HOME_OR_DRAW': 'double_chance', 'AWAY_OR_DRAW': 'double_chance',
            'BTTS_YES': 'btts', 'BTTS_NO': 'btts',
        }
        # Over/Under are their own market
        for k in bets:
            if k.startswith('OVER_') or k.startswith('UNDER_'):
                market_of[k] = 'totals'
        
        best_market = market_of.get(best_bet, 'other')
        
        for bet_name, prob in sorted(bets.items(), key=lambda x: x[1], reverse=True):
            if bet_name == best_bet:
                continue
            bet_market = market_of.get(bet_name, 'other')
            # Don't add conflicting bets from same market
            if bet_market == best_market:
                continue
            # Don't add double chance if we already have the straight win
            if bet_market == 'double_chance':
                continue
            if prob >= SECONDARY_THRESHOLD:
                secondary.append({'bet': bet_name, 'prob': prob})
        
        # Value detection
        implied_prob = 0.0
        value_edge = 0.0
        if match.bookmaker_odds:
            odds_map = {'HOME_WIN': 'home', 'AWAY_WIN': 'away', 'DRAW': 'draw'}
            odds_key = odds_map.get(best_bet)
            if odds_key and odds_key in match.bookmaker_odds:
                odds_val = match.bookmaker_odds[odds_key]
                val = self.value.detect_value(best_prob, odds_val)
                implied_prob = val['implied_probability']
                value_edge = val['value_edge']
        
        # Tier assignment
        tier = 'AVOID'
        if best_prob >= 0.72:
            tier = 'FIRE'
        elif best_prob >= 0.62:
            tier = 'SOLID'
        elif best_prob >= 0.55:
            tier = 'LEAN'
        
        analysis = {
            'home_strength': home_strength,
            'away_strength': away_strength,
            'strength_diff': strength_diff,
            'poisson_xg': xg,
            'all_bets': bets,
            'secondary_bets': secondary
        }
        
        return Prediction(
            match=match,
            recommended_bet=best_bet,
            confidence=best_prob,
            model_probability=best_prob,
            implied_probability=implied_prob,
            value_edge=value_edge,
            tier=tier,
            analysis=analysis
        )

    def predict_all_matches(self, matches: List[Match], h2h_data: Optional[Dict] = None) -> List[Prediction]:
        """Only FIRE and SOLID picks. No youth teams."""
        predictions = []
        h2h_data = h2h_data or {}
        
        # Filter garbage matches
        skip_keywords = ['U-19', 'U-21', 'U19', 'U21', 'U-20', 'U20', 'U-23', 'U23',
                         'Reserve', 'Youth', 'Women', 'Primavera', 'B Team', 'II']
        
        for match in matches:
            try:
                # Skip youth/reserve matches
                team_names = f"{match.home_team.name} {match.away_team.name} {match.league}"
                if any(kw.lower() in team_names.lower() for kw in skip_keywords):
                    continue
                
                pred = self.predict_match(match, h2h_data.get(match.id, []))
                
                # Skip MLB Over/Under (no pitcher data)
                if match.sport.lower() in ('baseball', 'mlb'):
                    if 'OVER' in pred.recommended_bet or 'UNDER' in pred.recommended_bet:
                        continue
                
                if pred.tier in ['FIRE', 'SOLID']:
                    predictions.append(pred)
            except Exception as e:
                logger.debug(f"Error predicting {match.id}: {e}")
        
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions

    def get_best_bets(self, matches: List[Match], h2h_data: Optional[Dict] = None, max_picks: int = 5) -> List[Prediction]:
        """Top 5 picks. Quality singles."""
        return self.predict_all_matches(matches, h2h_data)[:max_picks]
