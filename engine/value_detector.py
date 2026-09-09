import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ValueDetector:
    """
    Value Bet Detection & Bankroll Management.
    Because being right doesn't matter if the odds are garbage.
    """
    def __init__(self):
        pass
        
    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """Convert bookmaker decimal odds to implied probability."""
        if decimal_odds <= 1.0:
            return 1.0
        return 1.0 / decimal_odds
        
    def detect_value(self, model_probability: float, bookmaker_odds: float, min_edge: float = 0.10) -> Dict[str, Any]:
        """Detect if there's mathematical value in a bet."""
        implied = self.calculate_implied_probability(bookmaker_odds)
        edge = model_probability - implied
        
        # Expected value: (Probability of Winning × Amount Won per Bet) − (Probability of Losing × Stake)
        expected_value = (model_probability * (bookmaker_odds - 1)) - (1 - model_probability)
        
        has_value = edge >= min_edge and expected_value > 0
        
        kelly = self.kelly_criterion(model_probability, bookmaker_odds)
        
        return {
            'model_probability': model_probability,
            'implied_probability': implied,
            'value_edge': edge,
            'expected_value': expected_value,
            'has_value': has_value,
            'kelly_fraction': kelly
        }
        
    def kelly_criterion(self, probability: float, odds: float, fraction: float = 0.25) -> float:
        """
        Calculate optimal bet size using Kelly Criterion.
        We default to quarter-Kelly because full Kelly is a rollercoaster.
        """
        if odds <= 1.0:
            return 0.0
            
        b = odds - 1.0
        p = probability
        q = 1.0 - p
        
        # Kelly formula: f* = (bp - q) / b
        full_kelly = (b * p - q) / b
        
        if full_kelly <= 0:
            return 0.0
            
        # Apply fraction (e.g. Quarter Kelly)
        adjusted_kelly = full_kelly * fraction
        
        # Never risk more than 10% of bankroll on a single bet
        return min(0.10, adjusted_kelly)
        
    def recommended_stake(self, bankroll: float, probability: float, odds: float) -> float:
        """Calculate actual dollar amount to stake based on bankroll."""
        fraction = self.kelly_criterion(probability, odds)
        stake = bankroll * fraction
        return round(stake, 2)
