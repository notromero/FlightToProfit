"""
Results Tracker v2 — Checks game results and reports W/L automatically.
Handles ALL 16+ bet types. Human-readable labels for public community.
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


def _bet_display_name(bet_code: str, home: str = '', away: str = '') -> str:
    """Convert raw bet codes to clean human-readable names."""
    mapping = {
        'HOME_WIN': f'{home} Win',
        'AWAY_WIN': f'{away} Win',
        'DRAW': 'Draw',
        'HOME_OR_DRAW': f'{home} or Draw (1X)',
        'AWAY_OR_DRAW': f'{away} or Draw (X2)',
        'BTTS_YES': 'BTTS Yes',
        'BTTS_NO': 'BTTS No',
        'CLEAN_SHEET_HOME': f'{home} Clean Sheet',
        'CLEAN_SHEET_AWAY': f'{away} Clean Sheet',
        'HOME_WIN_TO_NIL': f'{home} Win to Nil',
        'AWAY_WIN_TO_NIL': f'{away} Win to Nil',
        'HOME_-1.5': f'{home} -1.5 Handicap',
        'AWAY_+1.5': f'{away} +1.5 Handicap',
        'HOME_OVER_0.5': f'{home} Over 0.5 Goals',
        'HOME_OVER_1.5': f'{home} Over 1.5 Goals',
        'AWAY_OVER_0.5': f'{away} Over 0.5 Goals',
        'AWAY_OVER_1.5': f'{away} Over 1.5 Goals',
    }
    
    # Direct lookup
    if bet_code in mapping:
        return mapping[bet_code]
    
    # Over/Under lines
    if bet_code.startswith('OVER_'):
        line = bet_code.replace('OVER_', '')
        return f'Over {line} Goals'
    if bet_code.startswith('UNDER_'):
        line = bet_code.replace('UNDER_', '')
        return f'Under {line} Goals'
    
    return bet_code


def check_bet_result(pick: dict, home_score: int, away_score: int) -> str:
    """Check if a bet won or lost given final scores. Handles ALL bet types."""
    bet = pick['recommended_bet']
    total = home_score + away_score
    margin = home_score - away_score  # positive = home won by X
    
    # --- MATCH RESULT ---
    if bet == 'HOME_WIN':
        return 'won' if home_score > away_score else 'lost'
    elif bet == 'AWAY_WIN':
        return 'won' if away_score > home_score else 'lost'
    elif bet == 'DRAW':
        return 'won' if home_score == away_score else 'lost'
    
    # --- DOUBLE CHANCE ---
    elif bet == 'HOME_OR_DRAW':
        return 'won' if home_score >= away_score else 'lost'
    elif bet == 'AWAY_OR_DRAW':
        return 'won' if away_score >= home_score else 'lost'
    
    # --- BTTS ---
    elif bet == 'BTTS_YES':
        return 'won' if home_score > 0 and away_score > 0 else 'lost'
    elif bet == 'BTTS_NO':
        return 'won' if home_score == 0 or away_score == 0 else 'lost'
    
    # --- OVER/UNDER ---
    elif bet.startswith('OVER_'):
        line = float(bet.replace('OVER_', ''))
        return 'won' if total > line else 'lost'
    elif bet.startswith('UNDER_'):
        line = float(bet.replace('UNDER_', ''))
        return 'won' if total < line else 'lost'
    
    # --- HANDICAP ---
    elif bet == 'HOME_-1.5':
        # Home team must win by 2+ goals
        return 'won' if margin >= 2 else 'lost'
    elif bet == 'AWAY_+1.5':
        # Away team +1.5 = away team doesn't lose by 2+
        # Won if: away wins, draw, or loses by exactly 1
        return 'won' if margin < 2 else 'lost'
    elif bet == 'HOME_+1.5':
        return 'won' if margin > -2 else 'lost'
    elif bet == 'AWAY_-1.5':
        return 'won' if (away_score - home_score) >= 2 else 'lost'
    
    # --- CLEAN SHEET ---
    elif bet == 'CLEAN_SHEET_HOME':
        return 'won' if away_score == 0 else 'lost'
    elif bet == 'CLEAN_SHEET_AWAY':
        return 'won' if home_score == 0 else 'lost'
    
    # --- WIN TO NIL ---
    elif bet == 'HOME_WIN_TO_NIL':
        return 'won' if home_score > 0 and away_score == 0 else 'lost'
    elif bet == 'AWAY_WIN_TO_NIL':
        return 'won' if away_score > 0 and home_score == 0 else 'lost'
    
    # --- TEAM TOTALS ---
    elif bet == 'HOME_OVER_0.5':
        return 'won' if home_score >= 1 else 'lost'
    elif bet == 'HOME_OVER_1.5':
        return 'won' if home_score >= 2 else 'lost'
    elif bet == 'AWAY_OVER_0.5':
        return 'won' if away_score >= 1 else 'lost'
    elif bet == 'AWAY_OVER_1.5':
        return 'won' if away_score >= 2 else 'lost'
    
    return 'unknown'


def check_secondary_result(sb: dict, home_score: int, away_score: int) -> str:
    """Check secondary bet result."""
    fake_pick = {'recommended_bet': sb['bet']}
    return check_bet_result(fake_pick, home_score, away_score)


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
            'result': 'pending',
            'home_score': None,
            'away_score': None,
            'checked': False
        }
        picks.append(pick)
    
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


async def check_results(espn_client) -> Optional[str]:
    """Check ESPN for final scores and update picks."""
    picks = load_picks()
    if not picks:
        return None
    
    pending = [p for p in picks if p['result'] == 'pending']
    if not pending:
        return None
    
    try:
        matches = espn_client.get_todays_matches()
    except Exception as e:
        logger.error(f"Error fetching results: {e}")
        return None
    
    match_lookup = {m.id: m for m in matches}
    new_results = []
    
    for pick in picks:
        if pick['result'] != 'pending':
            continue
        
        match = match_lookup.get(pick['match_id'])
        if not match:
            continue
        
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
            
            for sb in pick.get('secondary_bets', []):
                sb['result'] = check_secondary_result(sb, hs, aws)
            
            new_results.append(pick)
    
    if not new_results:
        return None
    
    with open(PICKS_FILE, 'w') as f:
        json.dump(picks, f, indent=2)
    
    # --- BUILD CLEAN RESULTS MESSAGE ---
    msg = "📊 RESULTS UPDATE\n━━━━━━━━━━━━━━━━━\n\n"
    
    for pick in new_results:
        home = pick['home_team']
        away = pick['away_team']
        score = f"{pick['home_score']}:{pick['away_score']}"
        icon = "✅" if pick['result'] == 'won' else "❌"
        bet_name = _bet_display_name(pick['recommended_bet'], home, away)
        conf = f"{pick['confidence']*100:.0f}%"
        
        msg += f"{icon} {home} vs {away} ({score})\n"
        msg += f"   Pick: {bet_name} @ {conf} — {'WON ✅' if pick['result'] == 'won' else 'LOST ❌'}\n"
        
        for sb in pick.get('secondary_bets', []):
            if 'result' in sb:
                sb_icon = "✅" if sb['result'] == 'won' else "❌"
                sb_name = _bet_display_name(sb['bet'], home, away)
                sb_conf = f"{sb['prob']*100:.0f}%"
                msg += f"   {sb_icon} ➕ {sb_name} @ {sb_conf} — {'WON' if sb['result'] == 'won' else 'LOST'}\n"
        msg += "\n"
    
    # Check if ALL picks resolved
    all_resolved = all(p['result'] != 'pending' for p in picks)
    
    if all_resolved:
        # Count main picks only (not secondaries)
        wins = sum(1 for p in picks if p['result'] == 'won')
        losses = sum(1 for p in picks if p['result'] == 'lost')
        total_picks = wins + losses
        wr = (wins / total_picks * 100) if total_picks > 0 else 0
        
        # Also count all bets (main + secondary)
        all_wins = wins
        all_losses = losses
        for p in picks:
            for sb in p.get('secondary_bets', []):
                if sb.get('result') == 'won':
                    all_wins += 1
                elif sb.get('result') == 'lost':
                    all_losses += 1
        all_total = all_wins + all_losses
        all_wr = (all_wins / all_total * 100) if all_total > 0 else 0
        
        indicator = "🟢" if wr >= 60 else "🟡" if wr >= 40 else "🔴"
        
        msg += "━━━━━━━━━━━━━━━━━\n"
        msg += f"📈 TODAY'S FINAL:\n"
        msg += f"   Main Picks: {wins}W - {losses}L ({wr:.0f}%) {indicator}\n"
        msg += f"   All Bets: {all_wins}W - {all_losses}L ({all_wr:.0f}%)\n"
        msg += f"FlightToProfit ✈️\n"
        
        # Clear picks file after midnight
        now = datetime.now(BEIRUT)
        if now.hour >= 23:
            os.remove(PICKS_FILE)
    else:
        pending_count = sum(1 for p in picks if p['result'] == 'pending')
        msg += f"⏳ {pending_count} game(s) still pending\n"
        msg += f"FlightToProfit ✈️\n"
    
    return msg
