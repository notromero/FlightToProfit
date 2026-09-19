"""
Predictor v5 — MASKED BETTOR EDGE MODEL.
Weather + Pitcher + Fatigue + Signal Stack + Draw Trap + Storyline.
Only 3 max picks. Quality over quantity.
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
from engine.weather import WeatherEngine
from engine.pitcher import PitcherAnalyzer
from engine.fatigue import FatigueAnalyzer
from engine.signal_stack import SignalStack

logger = logging.getLogger(__name__)


class Predictor:
    def __init__(self):
        self.elo = EloRating()
        self.poisson = PoissonModel()
        self.form = FormAnalyzer()
        self.h2h = H2HAnalyzer()
        self.value = ValueDetector()
        self.weather = WeatherEngine()
        self.pitcher = PitcherAnalyzer()
        self.fatigue = FatigueAnalyzer()
        self.signals = SignalStack()

    def _team_strength(self, team: Team, is_home: bool, 
                       pitcher_rating: int = 50, fatigue_adj: float = 0) -> float:
        """Team strength 0-100 with trending form + xG regression + pitcher + fatigue."""
        score = 50.0

        # Elo (biggest factor)
        elo_diff = team.elo_rating - 1500
        score += elo_diff * 0.02

        # --- TRENDING FORM (Masked Bettor method) ---
        form_data = self.form.analyze_form(team)
        trending_ppg = form_data.get('trending_ppg', 1.0)
        # Trending PPG ranges ~0-3, center at 1.5 for average
        score += (trending_ppg - 1.5) * 5

        # Form trend bonus/penalty
        trend = form_data.get('form_trend', 'STABLE')
        if trend == 'IMPROVING':
            score += 3
        elif trend == 'DECLINING':
            score -= 3

        # xG regression adjustment
        xg_flag = form_data.get('xg_flag', 'NEUTRAL')
        if xg_flag == 'OVERPERFORMER':
            score -= 4  # Regression coming, penalize
        elif xg_flag == 'UNDERPERFORMER':
            score += 4  # Bounce coming, boost
        elif xg_flag == 'GENUINE':
            score += 2  # Truly dominant, small boost

        # Record (static form — less weight)
        w, l, d = team.overall_record
        total = w + l + d
        if total > 0:
            win_pct = w / total
            score += (win_pct - 0.5) * 10  # Reduced from 20

        # --- HOME/AWAY SPLIT (never mix them) ---
        if is_home:
            hw, hl, hd = team.home_record
            h_total = hw + hl + hd
            if h_total >= 3:
                home_pct = hw / h_total
                score += (home_pct - 0.5) * 8  # Home-specific boost
            score += 4  # Base home advantage
        else:
            aw, al, ad = team.away_record
            a_total = aw + al + ad
            if a_total >= 3:
                away_pct = aw / a_total
                score += (away_pct - 0.5) * 8  # Away-specific

        # Goal differential
        if team.goals_scored_last_n and team.goals_conceded_last_n:
            avg_scored = np.mean(team.goals_scored_last_n)
            avg_conceded = np.mean(team.goals_conceded_last_n)
            score += (avg_scored - avg_conceded) * 3

        # Pitcher impact (MLB only — weighted 25% of total)
        if pitcher_rating != 50:
            pitcher_diff = (pitcher_rating - 50) * 0.25
            score += pitcher_diff

        # Fatigue penalty
        score += fatigue_adj

        return max(10, min(90, score))

    def predict_match(self, match: Match, h2h: list = None,
                      pitcher_data: dict = None, weather_data: dict = None) -> Prediction:
        home = match.home_team
        away = match.away_team
        is_soccer = match.sport.lower() in ('soccer', 'football')
        is_baseball = match.sport.lower() in ('baseball', 'mlb')

        # --- WEATHER ---
        weather_impact = {'total_adjustment': 1.0, 'home_boost': 0, 'flags': [], 'summary': ''}
        if weather_data:
            weather_impact = self.weather.calculate_weather_impact(weather_data, match.sport)

        # --- PITCHER ---
        home_pitcher_rating = {'rating': 50, 'grade': 'UNKNOWN', 'era': 0, 'whip': 0, 'k9': 0, 'name': ''}
        away_pitcher_rating = {'rating': 50, 'grade': 'UNKNOWN', 'era': 0, 'whip': 0, 'k9': 0, 'name': ''}
        pitcher_edge = {'edge_team': 'neutral', 'edge_size': 0, 'summary': ''}

        if is_baseball and pitcher_data:
            hp_id = pitcher_data.get('home_pitcher_id')
            ap_id = pitcher_data.get('away_pitcher_id')
            if hp_id:
                hp_stats = self.pitcher.get_starter_stats(hp_id)
                if hp_stats:
                    home_pitcher_rating = self.pitcher.rate_pitcher(hp_stats)
            if ap_id:
                ap_stats = self.pitcher.get_starter_stats(ap_id)
                if ap_stats:
                    away_pitcher_rating = self.pitcher.rate_pitcher(ap_stats)
            pitcher_edge = self.pitcher.get_matchup_edge(home_pitcher_rating, away_pitcher_rating)

        # --- FATIGUE ---
        # Simple: check travel penalty for away team
        travel = self.fatigue.check_travel(home.name, away.name)
        away_fatigue = travel.get('away_travel_penalty', 0)

        # --- TEAM STRENGTH ---
        home_strength = self._team_strength(
            home, is_home=True,
            pitcher_rating=home_pitcher_rating['rating'],
            fatigue_adj=weather_impact.get('home_boost', 0) * 100
        )
        away_strength = self._team_strength(
            away, is_home=False,
            pitcher_rating=away_pitcher_rating['rating'],
            fatigue_adj=away_fatigue
        )

        strength_diff = home_strength - away_strength

        # Win probabilities
        home_win_prob = 1.0 / (1.0 + 10 ** (-strength_diff / 15.0))
        away_win_prob = 1.0 - home_win_prob

        # Soccer draw carving
        draw_prob = 0.0
        if is_soccer:
            base_draw = 0.26
            draw_reduction = min(0.20, abs(strength_diff) * 0.015)
            draw_prob = max(0.05, base_draw - draw_reduction)
            total_win = home_win_prob + away_win_prob
            home_win_prob = home_win_prob / total_win * (1.0 - draw_prob)
            away_win_prob = away_win_prob / total_win * (1.0 - draw_prob)

        # --- POISSON (weather-adjusted) ---
        home_att, home_def = self.poisson.calculate_attack_defense(home, sport=match.sport)
        away_att, away_def = self.poisson.calculate_attack_defense(away, sport=match.sport)
        
        weather_adj = weather_impact.get('total_adjustment', 1.0)
        xg = self.poisson.predict_score(home_att, home_def, away_att, away_def, weather_adj=weather_adj)

        he = xg['home_expected']
        ae = xg['away_expected']

        # Pitcher-adjusted expected runs (MLB)
        if is_baseball:
            he = self.pitcher.adjust_expected_runs(he, away_pitcher_rating['rating'])  # away pitcher faces home batters
            ae = self.pitcher.adjust_expected_runs(ae, home_pitcher_rating['rating'])  # home pitcher faces away batters

        # --- BUILD ALL BETS ---
        bets = {}
        bets['HOME_WIN'] = home_win_prob
        bets['AWAY_WIN'] = away_win_prob

        if is_soccer:
            bets['DRAW'] = draw_prob
            # BTTS
            btts = self.poisson.btts_probability(he, ae)
            bets['BTTS_YES'] = btts['btts_yes']
            bets['BTTS_NO'] = btts['btts_no']
            # Double Chance
            bets['HOME_OR_DRAW'] = home_win_prob + draw_prob
            bets['AWAY_OR_DRAW'] = away_win_prob + draw_prob
            # Multiple O/U lines
            for line in [1.5, 2.5, 3.5]:
                ou = self.poisson.over_under_probability(he, ae, line)
                bets[f'OVER_{line}'] = ou['over']
                bets[f'UNDER_{line}'] = ou['under']
            # Clean Sheets
            bets['CLEAN_SHEET_HOME'] = self.poisson.clean_sheet_probability(ae)
            bets['CLEAN_SHEET_AWAY'] = self.poisson.clean_sheet_probability(he)
            # Win to Nil
            bets['HOME_WIN_TO_NIL'] = self.poisson.win_to_nil_probability(he, ae, 'home')
            bets['AWAY_WIN_TO_NIL'] = self.poisson.win_to_nil_probability(he, ae, 'away')
            # Handicap
            bets['HOME_-1.5'] = self.poisson.handicap_probability(he, ae, -1.5, 'home')
            bets['AWAY_+1.5'] = 1.0 - bets['HOME_-1.5']
            # Team totals
            bets['HOME_OVER_0.5'] = self.poisson.team_total_probability(he, 0.5, over=True)
            bets['AWAY_OVER_0.5'] = self.poisson.team_total_probability(ae, 0.5, over=True)
            bets['HOME_OVER_1.5'] = self.poisson.team_total_probability(he, 1.5, over=True)
            bets['AWAY_OVER_1.5'] = self.poisson.team_total_probability(ae, 1.5, over=True)
        else:
            # Baseball O/U lines
            for line in [7.5, 8.5, 9.5]:
                ou = self.poisson.over_under_probability(he, ae, line)
                bets[f'OVER_{line}'] = ou['over']
                bets[f'UNDER_{line}'] = ou['under']
            # Run line (handicap)
            bets['HOME_-1.5'] = self.poisson.handicap_probability(he, ae, -1.5, 'home')
            bets['AWAY_+1.5'] = 1.0 - bets['HOME_-1.5']

        # --- PICK BEST ---
        best_bet = max(bets, key=bets.get)
        best_prob = bets[best_bet]

        # --- SECONDARY BETS ---
        SECONDARY_THRESHOLD = 0.55
        MAX_SECONDARY = 3
        secondary = []

        market_of = {
            'HOME_WIN': 'winner', 'AWAY_WIN': 'winner', 'DRAW': 'winner',
            'HOME_OR_DRAW': 'dc', 'AWAY_OR_DRAW': 'dc',
            'BTTS_YES': 'btts', 'BTTS_NO': 'btts',
            'CLEAN_SHEET_HOME': 'cs', 'CLEAN_SHEET_AWAY': 'cs',
            'HOME_WIN_TO_NIL': 'wtn', 'AWAY_WIN_TO_NIL': 'wtn',
            'HOME_-1.5': 'handicap', 'AWAY_+1.5': 'handicap',
            'HOME_OVER_0.5': 'ht_home', 'AWAY_OVER_0.5': 'ht_away',
            'HOME_OVER_1.5': 'ht_home2', 'AWAY_OVER_1.5': 'ht_away2',
        }
        for k in bets:
            if k.startswith('OVER_') or k.startswith('UNDER_'):
                market_of[k] = f'totals_{k}'

        best_market = market_of.get(best_bet, 'other')

        for bet_name, prob in sorted(bets.items(), key=lambda x: x[1], reverse=True):
            if len(secondary) >= MAX_SECONDARY:
                break
            if bet_name == best_bet:
                continue
            bet_market = market_of.get(bet_name, 'other')
            if bet_market == best_market:
                continue
            # Skip double chance and team totals as secondary (too obvious)
            if bet_market in ('dc', 'ht_home', 'ht_away', 'ht_home2', 'ht_away2'):
                continue
            if prob >= SECONDARY_THRESHOLD:
                secondary.append({'bet': bet_name, 'prob': prob})

        # --- VALUE ---
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

        # --- TIER ---
        tier = 'AVOID'
        if best_prob >= 0.72:
            tier = 'FIRE'
        elif best_prob >= 0.62:
            tier = 'SOLID'
        elif best_prob >= 0.55:
            tier = 'LEAN'

        # --- EDGE EXPLANATION ---
        edge_reasons = []
        if pitcher_edge.get('edge_size', 0) >= 10:
            edge_reasons.append(f"⚾ {pitcher_edge['summary']}")
        if weather_impact.get('flags'):
            edge_reasons.append(weather_impact['summary'])
        if strength_diff > 15:
            edge_reasons.append(f"💪 {abs(strength_diff):.0f}pt strength gap")
        elif strength_diff < -15:
            edge_reasons.append(f"💪 {abs(strength_diff):.0f}pt strength gap (away)")

        # Trending form edges
        home_form = self.form.analyze_form(home)
        away_form = self.form.analyze_form(away)
        if home_form.get('form_trend') == 'IMPROVING' and 'HOME' in best_bet:
            edge_reasons.append(f"📈 {home.name} trending UP")
        if away_form.get('form_trend') == 'DECLINING' and 'HOME' in best_bet:
            edge_reasons.append(f"📉 {away.name} trending DOWN")
        if away_form.get('form_trend') == 'IMPROVING' and 'AWAY' in best_bet:
            edge_reasons.append(f"📈 {away.name} trending UP")

        # xG regression flags
        if home_form.get('xg_flag') == 'OVERPERFORMER' and 'AWAY' in best_bet:
            edge_reasons.append(f"⚠️ {home.name} overperforming — regression due")
        if away_form.get('xg_flag') == 'OVERPERFORMER' and 'HOME' in best_bet:
            edge_reasons.append(f"⚠️ {away.name} overperforming — regression due")

        analysis = {
            'home_strength': home_strength,
            'away_strength': away_strength,
            'strength_diff': strength_diff,
            'poisson_xg': {'home_expected': he, 'away_expected': ae},
            'all_bets': bets,
            'secondary_bets': secondary,
            'weather': weather_data or {},
            'weather_impact': weather_impact,
            'pitcher_edge': pitcher_edge,
            'home_pitcher': home_pitcher_rating,
            'away_pitcher': away_pitcher_rating,
            'edge_reasons': edge_reasons,
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

    def predict_all_matches(self, matches: List[Match], h2h_data: Optional[Dict] = None,
                            pitcher_map: Optional[Dict] = None) -> List[Prediction]:
        """Only FIRE and SOLID picks. No youth teams."""
        predictions = []
        h2h_data = h2h_data or {}
        pitcher_map = pitcher_map or {}

        skip_keywords = ['U-19', 'U-21', 'U19', 'U21', 'U-20', 'U20', 'U-23', 'U23',
                         'Reserve', 'Youth', 'Women', 'Primavera', 'B Team', 'II']

        for match in matches:
            try:
                team_names = f"{match.home_team.name} {match.away_team.name} {match.league}"
                if any(kw.lower() in team_names.lower() for kw in skip_keywords):
                    continue

                # Get weather
                weather_data = None
                if match.venue and match.start_time:
                    try:
                        weather_data = self.weather.get_game_weather(
                            match.venue, match.start_time.isoformat()
                        )
                    except Exception:
                        pass

                # Get pitcher data for MLB
                pitcher_data = pitcher_map.get(match.id, {})

                pred = self.predict_match(
                    match, h2h_data.get(match.id, []),
                    pitcher_data=pitcher_data,
                    weather_data=weather_data
                )

                if pred.tier in ['FIRE', 'SOLID']:
                    predictions.append(pred)
            except Exception as e:
                logger.debug(f"Error predicting {match.id}: {e}")

        predictions.sort(key=lambda p: p.confidence, reverse=True)
        return predictions

    def get_best_bets(self, matches: List[Match], h2h_data: Optional[Dict] = None,
                      pitcher_map: Optional[Dict] = None, max_picks: int = 3) -> List[Prediction]:
        """Top 3 picks max. Signal stack filtered. Quality over quantity."""
        all_preds = self.predict_all_matches(matches, h2h_data, pitcher_map)
        
        # Build match map for signal stack
        matches_map = {m.id: m for m in matches}
        
        # Run signal stack — kills draw traps, filters by stars, caps at 3
        filtered = self.signals.filter_predictions(all_preds, matches_map, min_stars=2)
        
        return filtered[:max_picks]
