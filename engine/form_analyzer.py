"""
Form Analyzer v2 — Masked Bettor method.
Trending form (weighted recent) vs Static form (season average).
xG regression detection: overperformers get penalized, underperformers get boosted.
Home/Away form split — never mix them.
"""
import logging
import numpy as np
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FormAnalyzer:
    def __init__(self):
        pass

    def analyze_form(self, team: Any, n_games: int = 10) -> Dict[str, Any]:
        """Full form analysis with trending vs static split."""
        form_list = team.recent_form[:n_games]
        if not form_list:
            return self._empty_form()

        # Points: W=3, D=1, L=0 (standard football points)
        pts_map = {'W': 3, 'D': 1, 'L': 0}
        points = [pts_map.get(r.upper(), 0) for r in form_list]

        # --- TRENDING FORM (last 5, weighted heavily) ---
        last5 = points[:5] if len(points) >= 5 else points
        # Weights: most recent = 1.0, oldest = 0.5
        weights_5 = [1.0 - (i * 0.1) for i in range(len(last5))]
        trending_ppg = sum(p * w for p, w in zip(last5, weights_5)) / sum(weights_5)

        # --- STATIC FORM (all n games, flat average) ---
        static_ppg = sum(points) / len(points)

        # --- TREND DIRECTION ---
        mid = len(points) // 2
        recent_half = points[:mid] if mid > 0 else points
        older_half = points[mid:]
        recent_avg = np.mean(recent_half) if recent_half else 1.0
        older_avg = np.mean(older_half) if older_half else 1.0

        if recent_avg > older_avg + 0.3:
            trend = 'IMPROVING'
            trend_emoji = '📈'
        elif recent_avg < older_avg - 0.3:
            trend = 'DECLINING'
            trend_emoji = '📉'
        else:
            trend = 'STABLE'
            trend_emoji = '➡️'

        # --- DIVERGENCE: trending vs static ---
        # If trending >> static: team is getting better (value on them)
        # If trending << static: team is getting worse (fade them)
        divergence = trending_ppg - static_ppg
        if divergence > 0.4:
            divergence_flag = 'OUTPERFORMING'  # trending up vs season avg
        elif divergence < -0.4:
            divergence_flag = 'UNDERPERFORMING'  # trending down vs season avg
        else:
            divergence_flag = 'ALIGNED'

        # Goal stats
        gs = team.goals_scored_last_n[:n_games] if team.goals_scored_last_n else []
        gc = team.goals_conceded_last_n[:n_games] if team.goals_conceded_last_n else []

        avg_scored = float(np.mean(gs)) if gs else 0.0
        avg_conceded = float(np.mean(gc)) if gc else 0.0

        # --- xG REGRESSION PROXY ---
        # Without actual xG data, we approximate:
        # If scoring way more than conceding in wins but barely winning = overperformer
        # If losing close games with good goal stats = underperformer (due for bounce)
        xg_flag = self._xg_regression_proxy(form_list, gs, gc)

        # Clean sheets
        clean_sheets = sum(1 for g in gc if g == 0) if gc else 0
        cs_rate = clean_sheets / len(gc) if gc else 0.0

        # Recent scoring trend (last 3 vs prev 3)
        scoring_trend = 'STABLE'
        if len(gs) >= 6:
            recent_scoring = np.mean(gs[:3])
            older_scoring = np.mean(gs[3:6])
            if recent_scoring > older_scoring + 0.5:
                scoring_trend = 'SCORING_MORE'
            elif recent_scoring < older_scoring - 0.5:
                scoring_trend = 'SCORING_LESS'

        # Form rating 0-1 (blend trending 70% + static 30%)
        form_rating = (trending_ppg * 0.7 + static_ppg * 0.3) / 3.0  # normalize to 0-1
        form_rating = max(0.0, min(1.0, form_rating))

        win_rate = form_list.count('W') / len(form_list) if form_list else 0
        
        summary = f"{trend_emoji} {trend} | PPG: {trending_ppg:.1f} trending, {static_ppg:.1f} static"
        if divergence_flag != 'ALIGNED':
            summary += f" | ⚠️ {divergence_flag}"

        return {
            'form_rating': form_rating,
            'win_rate': win_rate,
            'trending_ppg': trending_ppg,
            'static_ppg': static_ppg,
            'avg_scored': avg_scored,
            'avg_conceded': avg_conceded,
            'clean_sheet_rate': cs_rate,
            'clean_sheets': clean_sheets,
            'form_trend': trend,
            'trend_emoji': trend_emoji,
            'divergence': divergence_flag,
            'xg_flag': xg_flag,
            'scoring_trend': scoring_trend,
            'summary': summary
        }

    def _xg_regression_proxy(self, form: list, gs: list, gc: list) -> str:
        """
        Approximate xG regression without actual xG data.
        Uses goal distribution patterns to detect luck.
        """
        if len(gs) < 5 or len(gc) < 5:
            return 'NEUTRAL'

        wins = form[:5].count('W') if len(form) >= 5 else 0
        avg_scored = np.mean(gs[:5])
        avg_conceded = np.mean(gc[:5])
        goal_diff = avg_scored - avg_conceded

        # Winning a lot but barely outscoring opponents = lucky/overperformer
        if wins >= 4 and goal_diff < 0.5:
            return 'OVERPERFORMER'  # winning tight games = regression coming

        # Losing a lot but outscoring opponents = unlucky/underperformer
        losses = form[:5].count('L') if len(form) >= 5 else 0
        if losses >= 3 and goal_diff > 0:
            return 'UNDERPERFORMER'  # losing despite creating more = bounce coming

        # Winning big = genuinely good
        if wins >= 3 and goal_diff > 1.5:
            return 'GENUINE'  # dominating, no regression expected

        return 'NEUTRAL'

    def _empty_form(self) -> dict:
        return {
            'form_rating': 0.5, 'win_rate': 0.5,
            'trending_ppg': 1.0, 'static_ppg': 1.0,
            'avg_scored': 0.0, 'avg_conceded': 0.0,
            'clean_sheet_rate': 0.0, 'clean_sheets': 0,
            'form_trend': 'STABLE', 'trend_emoji': '➡️',
            'divergence': 'ALIGNED', 'xg_flag': 'NEUTRAL',
            'scoring_trend': 'STABLE',
            'summary': 'Insufficient data'
        }

    def compare_form(self, team_a: Any, team_b: Any) -> Dict[str, Any]:
        """Compare trending form between two teams."""
        form_a = self.analyze_form(team_a)
        form_b = self.analyze_form(team_b)

        edge = form_a['trending_ppg'] - form_b['trending_ppg']

        if edge > 0.3:
            adv = 'team_a'
        elif edge < -0.3:
            adv = 'team_b'
        else:
            adv = 'even'

        return {
            'team_a_form': form_a,
            'team_b_form': form_b,
            'form_advantage': adv,
            'form_edge': float(edge)
        }
