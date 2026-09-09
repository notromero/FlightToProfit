import logging
import numpy as np
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FormAnalyzer:
    """
    Recent Form Analyzer. Captures the 'hot hand' or 'cold streak' effect.
    Exponential decay ensures we care more about last weekend than last month.
    """
    def __init__(self):
        pass
        
    def analyze_form(self, team: Any, n_games: int = 10) -> Dict[str, Any]:
        """Analyze a team's recent form based on recent W/L/D and goals."""
        form_list = team.recent_form[:n_games]
        if not form_list:
            return {
                'form_rating': 0.5,
                'win_rate': 0.5,
                'weighted_win_rate': 0.5,
                'avg_scored': 0.0,
                'avg_conceded': 0.0,
                'clean_sheet_rate': 0.0,
                'form_trend': 'STABLE',
                'summary': 'Insufficient data for form analysis.'
            }
            
        # Parse points (W=1, D=0.5, L=0)
        points = []
        for result in form_list:
            if result.upper() == 'W': points.append(1.0)
            elif result.upper() == 'D': points.append(0.5)
            else: points.append(0.0)
            
        # Exponential decay weights: weight[i] = 0.9^(n-1-i) (most recent is last in list?)
        # Assuming list is chronologically ordered [oldest, ..., newest] or vice versa.
        # Let's assume index 0 is newest for safety if standard descending list.
        # We will map index 0 to max weight.
        weights = [0.9 ** i for i in range(len(points))]
        weighted_points = sum(p * w for p, w in zip(points, weights))
        weighted_win_rate = weighted_points / sum(weights)
        win_rate = sum(points) / len(points)
        
        # Goal stats
        goals_scored = team.goals_scored_last_n[:n_games] if team.goals_scored_last_n else []
        goals_conceded = team.goals_conceded_last_n[:n_games] if team.goals_conceded_last_n else []
        
        avg_scored = float(np.mean(goals_scored)) if goals_scored else 0.0
        avg_conceded = float(np.mean(goals_conceded)) if goals_conceded else 0.0
        
        clean_sheets = sum(1 for g in goals_conceded if g == 0) if goals_conceded else 0
        clean_sheet_rate = clean_sheets / len(goals_conceded) if goals_conceded else 0.0
        
        # Trend (first half of form vs second half)
        mid = len(points) // 2
        recent_half = points[:mid] # Assuming 0 is newest
        older_half = points[mid:]
        
        recent_avg = np.mean(recent_half) if recent_half else 0.5
        older_avg = np.mean(older_half) if older_half else 0.5
        
        if recent_avg > older_avg + 0.1:
            trend = 'IMPROVING'
        elif recent_avg < older_avg - 0.1:
            trend = 'DECLINING'
        else:
            trend = 'STABLE'
            
        # Base form rating 0 to 1
        form_rating = weighted_win_rate
        
        summary = f"Rating: {form_rating:.2f} | Trend: {trend} | WR: {win_rate*100:.0f}%"
        
        return {
            'form_rating': form_rating,
            'win_rate': win_rate,
            'weighted_win_rate': weighted_win_rate,
            'avg_scored': avg_scored,
            'avg_conceded': avg_conceded,
            'clean_sheet_rate': clean_sheet_rate,
            'form_trend': trend,
            'summary': summary
        }

    def compare_form(self, team_a: Any, team_b: Any) -> Dict[str, Any]:
        """Compare form between two teams to find the edge."""
        form_a = self.analyze_form(team_a)
        form_b = self.analyze_form(team_b)
        
        edge = form_a['form_rating'] - form_b['form_rating']
        
        if edge > 0.1:
            adv = 'team_a'
        elif edge < -0.1:
            adv = 'team_b'
        else:
            adv = 'even'
            
        return {
            'team_a_form': form_a,
            'team_b_form': form_b,
            'form_advantage': adv,
            'form_edge': float(edge)
        }
