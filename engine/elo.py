import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class EloRating:
    """
    Elo Rating System. Because not all teams are created equal, 
    and we need math to prove your buddy wrong about his favorite team.
    """
    def __init__(self, k_factor: int = 32, home_advantage: int = 65, initial_rating: float = 1500.0):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.ratings: Dict[str, float] = {}  # team_id -> rating
        
    def get_rating(self, team_id: str) -> float:
        """Fetch a team's rating. If they're new, give 'em the baseline."""
        return self.ratings.get(team_id, self.initial_rating)
        
    def set_rating(self, team_id: str, rating: float) -> None:
        """Manually override a team's rating."""
        self.ratings[team_id] = rating
        
    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate the expected score (win probability) for team A against team B."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        
    def update_ratings(self, home_id: str, away_id: str, home_score: float, away_score: float) -> None:
        """Update ratings after a match, considering margin of victory."""
        home_rating = self.get_rating(home_id)
        away_rating = self.get_rating(away_id)
        
        # Add home field advantage
        home_adjusted = home_rating + self.home_advantage
        
        # Expected outcomes
        home_expected = self.expected_score(home_adjusted, away_rating)
        away_expected = self.expected_score(away_rating, home_adjusted)
        
        # Actual outcomes (1 for win, 0.5 for draw, 0 for loss)
        if home_score > away_score:
            home_actual, away_actual = 1.0, 0.0
        elif home_score < away_score:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual, away_actual = 0.5, 0.5
            
        # Margin of Victory (MoV) multiplier
        score_diff = abs(home_score - away_score)
        rating_diff = home_adjusted - away_rating if home_score > away_score else away_rating - home_adjusted
        mov_multiplier = math.log(score_diff + 1) * (2.2 / ((rating_diff * 0.001) + 2.2))
        if score_diff == 0:
            mov_multiplier = 1.0 # Draws have no MoV
            
        # The new ratings
        home_new = home_rating + self.k_factor * mov_multiplier * (home_actual - home_expected)
        away_new = away_rating + self.k_factor * mov_multiplier * (away_actual - away_expected)
        
        self.set_rating(home_id, home_new)
        self.set_rating(away_id, away_new)
        logger.debug(f"Elo update: {home_id} ({home_rating:.1f}->{home_new:.1f}), {away_id} ({away_rating:.1f}->{away_new:.1f})")

    def predict_match(self, home_id: str, away_id: str, sport: str = 'soccer') -> Dict[str, float]:
        """Predict win/draw/loss probabilities for a match."""
        home_rating = self.get_rating(home_id) + self.home_advantage
        away_rating = self.get_rating(away_id)
        
        home_prob = self.expected_score(home_rating, away_rating)
        away_prob = self.expected_score(away_rating, home_rating)
        
        if sport.lower() in ['soccer', 'football']:
            # Adjust for draws
            # A simple heuristic: closer the ratings, higher the draw chance
            rating_diff = abs(home_rating - away_rating)
            draw_prob = 0.30 * math.exp(-rating_diff / 200) # Peaks at 30% for even teams
            
            # Normalize remaining probability
            remaining = 1.0 - draw_prob
            norm_home = home_prob / (home_prob + away_prob) * remaining
            norm_away = away_prob / (home_prob + away_prob) * remaining
            
            return {'home_win': norm_home, 'draw': draw_prob, 'away_win': norm_away}
        else:
            # Sports without draws (e.g. basketball, baseball)
            total = home_prob + away_prob
            return {'home_win': home_prob / total, 'draw': 0.0, 'away_win': away_prob / total}
            
    def load_ratings(self, ratings_dict: Dict[str, float]) -> None:
        """Bulk load ratings."""
        self.ratings.update(ratings_dict)
        logger.info(f"Loaded {len(ratings_dict)} Elo ratings.")
        
    def get_all_ratings(self) -> Dict[str, float]:
        """Get all ratings for serialization."""
        return self.ratings.copy()
