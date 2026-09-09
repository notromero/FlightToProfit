"""
Results Tracker — Checks game results and reports W/L automatically.
Stores today's picks, polls ESPN for final scores, sends results to Telegram.
"""
import logging
import json
import os
import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

PICKS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'todays_picks.json')
BEIRUT = pytz.timezone('Asia/Beirut')


def save_picks(predictions: list):
    """Save today's picks to file for result tracking."""
    picks = []
    for p in predictions:
        match = p.match
        pick = {
            'match_id': match.id,
            'home_team': match.home_team.name,
            'away_team': match.away_team.name,
            'sport': match.sport,
            'league': match.league,
            'start_time': match.start_time.isoformat() if match.start_time else '',
            'recommended_bet': p.recommended_bet,
            'confidence': p.confidence,
            'tier': p.tier,
            'secondary_bets': p.analysis.get('secondary_bets', []),
            'result': 'pending',  # pending, won, lost
            'home_score': None,
            'away_score': None,
            'checked': False
        }
        picks.append(pick)
    
    # Load existing picks for today, don't overwrite
    existing = load_picks()
    existing_ids = {p['match_id'] for p in existing}
    
    for pick in picks:
        if pick['match_id'] not in existing_ids:
            existing.append(pick)
    
    os.makedirs(os.path.dirname(PICKS_FILE), exist_ok=True)
    with open(PICKS_FILE, 'w') as f:
        json.dump(existing, f, indent=2)
    
    logger.info(f"Saved {len(picks)} picks for tracking")


def load_picks() -> list:
    """Load today's saved picks."""
    if not os.path.exists(PICKS_FILE):
        return []
    try:
        with open(PICKS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def check_bet_result(pick: dict, home_score: int, away_score: int) -> str:
    """Check if a bet won or lost given final scores."""
    bet = pick['recommended_bet']
    total = home_score + away_score
    
    if bet == 'HOME_WIN':
        return 'won' if home_score > away_score else 'lost'
    elif bet == 'AWAY_WIN':
        return 'won' if away_score > home_score else 'lost'
    elif bet == 'DRAW':
        return 'won' if home_score == away_score else 'lost'
    elif bet == 'HOME_OR_DRAW':
        return 'won' if home_score >= away_score else 'lost'
    elif bet == 'AWAY_OR_DRAW':
        return 'won' if away_score >= home_score else 'lost'
    elif bet == 'BTTS_YES':
        return 'won' if home_score > 0 and away_score > 0 else 'lost'
    elif bet == 'BTTS_NO':
        return 'won' if home_score == 0 or away_score == 0 else 'lost'
    elif bet.startswith('OVER_'):
        line = float(bet.replace('OVER_', ''))
        return 'won' if total > line else 'lost'
    elif bet.startswith('UNDER_'):
        line = float(bet.replace('UNDER_', ''))
        return 'won' if total < line else 'lost'
    
    return 'unknown'


def check_secondary_result(sb: dict, home_score: int, away_score: int) -> str:
    """Check secondary bet result."""
    fake_pick = {'recommended_bet': sb['bet']}
    return check_bet_result(fake_pick, home_score, away_score)


async def check_results(espn_client) -> Optional[str]:
    """Check ESPN for final scores and update picks. Returns message if any results found."""
    picks = load_picks()
    if not picks:
        return None
    
    pending = [p for p in picks if p['result'] == 'pending']
    if not pending:
        return None
    
    # Get today's matches with scores
    try:
        matches = espn_client.get_todays_matches()
    except Exception as e:
        logger.error(f"Error fetching results: {e}")
        return None
    
    # Build lookup by match ID
    match_lookup = {}
    for m in matches:
        match_lookup[m.id] = m
    
    new_results = []
    
    for pick in picks:
        if pick['result'] != 'pending':
            continue
        
        match = match_lookup.get(pick['match_id'])
        if not match:
            continue
        
        # Check if game is final
        if match.status not in ('final', 'post', 'STATUS_FINAL'):
            if match.home_score is None:
                continue
        
        if match.home_score is not None and match.away_score is not None:
            hs = int(match.home_score)
            aws = int(match.away_score)
            
            pick['home_score'] = hs
            pick['away_score'] = aws
            pick['result'] = check_bet_result(pick, hs, aws)
            pick['checked'] = True
            
            # Check secondary bets too
            for sb in pick.get('secondary_bets', []):
                sb['result'] = check_secondary_result(sb, hs, aws)
            
            new_results.append(pick)
    
    if not new_results:
        return None
    
    # Save updated picks
    with open(PICKS_FILE, 'w') as f:
        json.dump(picks, f, indent=2)
    
    # Build results message
    msg = "📊 RESULTS UPDATE\n━━━━━━━━━━━━━━━━━\n\n"
    
    for pick in new_results:
        icon = "✅" if pick['result'] == 'won' else "❌"
        score = f"{pick['home_score']}:{pick['away_score']}"
        msg += f"{icon} {pick['home_team']} vs {pick['away_team']} ({score})\n"
        msg += f"   Pick: {pick['recommended_bet']} @ {pick['confidence']*100:.0f}% — {'WON' if pick['result'] == 'won' else 'LOST'}\n"
        
        for sb in pick.get('secondary_bets', []):
            if 'result' in sb:
                sb_icon = "✅" if sb['result'] == 'won' else "❌"
                msg += f"   {sb_icon} ➕ {sb['bet']} @ {sb['prob']*100:.0f}% — {'WON' if sb['result'] == 'won' else 'LOST'}\n"
        msg += "\n"
    
    # Check if ALL picks for today are resolved
    all_resolved = all(p['result'] != 'pending' for p in picks)
    
    if all_resolved:
        wins = sum(1 for p in picks if p['result'] == 'won')
        losses = sum(1 for p in picks if p['result'] == 'lost')
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        
        indicator = "🟢" if wr >= 60 else "🔴"
        msg += "━━━━━━━━━━━━━━━━━\n"
        msg += f"📈 TODAY'S FINAL: {wins}W - {losses}L ({wr:.0f}%) {indicator}\n"
        msg += f"FlightToProfit ✈️\n"
        
        # Clear picks file for tomorrow
        now = datetime.now(BEIRUT)
        if now.hour >= 23:
            os.remove(PICKS_FILE)
    else:
        pending_count = sum(1 for p in picks if p['result'] == 'pending')
        msg += f"⏳ {pending_count} game(s) still pending\n"
        msg += f"FlightToProfit ✈️\n"
    
    return msg
