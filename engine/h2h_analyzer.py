import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class H2HAnalyzer:
    """
    Head-to-Head Analyzer. Sometimes a team just has another team's number,
    regardless of current form or standings. We quantify that voodoo here.
    """
    def __init__(self):
        pass
        
    def analyze_h2h(self, team_a_id: str, team_b_id: str, past_meetings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze head-to-head match history between two teams.
        past_meetings: list of dicts with keys ['home_team_id', 'away_team_id', 'home_score', 'away_score']
        """
        if not past_meetings:
            return {
                'total_meetings': 0,
                'team_a_wins': 0,
                'team_b_wins': 0,
                'draws': 0,
                'avg_total_goals': 0.0,
                'dominant_team': None,
                'h2h_factor': 0.0,
                'summary': "No recent H2H history."
            }
            
        team_a_wins = 0
        team_b_wins = 0
        draws = 0
        total_goals = 0
        
        for match in past_meetings:
            home_id = str(match.get('home_team_id'))
            away_id = str(match.get('away_team_id'))
            home_score = float(match.get('home_score', 0))
            away_score = float(match.get('away_score', 0))
            
            total_goals += (home_score + away_score)
            
            if home_id == team_a_id:
                if home_score > away_score: team_a_wins += 1
                elif home_score < away_score: team_b_wins += 1
                else: draws += 1
            elif home_id == team_b_id:
                if home_score < away_score: team_a_wins += 1
                elif home_score > away_score: team_b_wins += 1
                else: draws += 1
                
        total_meetings = len(past_meetings)
        a_win_pct = team_a_wins / total_meetings
        b_win_pct = team_b_wins / total_meetings
        
        dominant_team: Optional[str] = None
        h2h_factor = 0.0
        
        # >60% win rate implies dominance
        if a_win_pct > 0.60:
            dominant_team = team_a_id
            h2h_factor = min(0.1, (a_win_pct - 0.5) * 0.2) # Up to +0.1 edge
        elif b_win_pct > 0.60:
            dominant_team = team_b_id
            h2h_factor = max(-0.1, -(b_win_pct - 0.5) * 0.2) # Down to -0.1 edge
            
        avg_total_goals = total_goals / total_meetings
        
        return {
            'total_meetings': total_meetings,
            'team_a_wins': team_a_wins,
            'team_b_wins': team_b_wins,
            'draws': draws,
            'avg_total_goals': avg_total_goals,
            'dominant_team': dominant_team,
            'h2h_factor': h2h_factor,
            'summary': f"{team_a_wins}W - {draws}D - {team_b_wins}L (from A's perspective)"
        }
