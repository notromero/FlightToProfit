from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class Team:
    id: str                    # unique team ID (espn ID or compound)
    name: str                  # display name (e.g., 'DET Tigers')
    abbreviation: str          # e.g., 'DET'
    sport: str                 # 'mlb', 'nba', 'soccer'
    league: str                # 'MLB', 'EPL', 'La Liga', etc.
    elo_rating: float = 1500.0
    recent_form: list = field(default_factory=list)  # list of recent results: 'W', 'L', 'D'
    goals_scored_last_n: list = field(default_factory=list)  # goals/runs in last N games
    goals_conceded_last_n: list = field(default_factory=list)
    home_record: tuple = (0, 0, 0)  # W, L, D
    away_record: tuple = (0, 0, 0)
    overall_record: tuple = (0, 0, 0)

@dataclass
class Match:
    id: str
    sport: str
    league: str
    home_team: Team
    away_team: Team
    start_time: datetime
    venue: str = ''
    status: str = 'scheduled'  # scheduled, live, final
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    bookmaker_odds: Optional[dict] = None  # {'home': 1.96, 'draw': 3.40, 'away': 4.20}

@dataclass
class Prediction:
    match: Match
    recommended_bet: str           # 'HOME_WIN', 'AWAY_WIN', 'DRAW', 'OVER_2.5', 'UNDER_2.5', 'BTTS_YES', 'BTTS_NO'
    confidence: float              # 0.0 to 1.0
    model_probability: float       # model's calculated probability
    implied_probability: float     # bookmaker's implied probability
    value_edge: float              # model_prob - implied_prob
    tier: str                      # 'FIRE', 'SOLID', 'LEAN', 'AVOID'
    analysis: dict                 # detailed analysis breakdown

@dataclass
class BetRecord:
    id: int = 0
    date: str = ''
    match_description: str = ''
    bet_type: str = ''
    odds: float = 0.0
    stake: float = 0.0
    result: str = ''  # 'win', 'loss', 'pending'
    profit: float = 0.0
