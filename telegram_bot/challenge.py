"""
Challenge Tracker — Bankroll challenges ($10 to $10K etc.)
Tracks daily progress, win streaks, and generates marketing content.
"""
import json
import os
import pytz
from datetime import datetime
from typing import Optional

CHALLENGE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'challenge.json')
BEIRUT = pytz.timezone('Asia/Beirut')


def _load_challenge() -> Optional[dict]:
    if not os.path.exists(CHALLENGE_FILE):
        return None
    try:
        with open(CHALLENGE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def _save_challenge(data: dict):
    os.makedirs(os.path.dirname(CHALLENGE_FILE), exist_ok=True)
    with open(CHALLENGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def start_challenge(start_amount: float, target: float, days: int) -> str:
    """Start a new bankroll challenge."""
    now = datetime.now(BEIRUT)
    data = {
        'start_amount': start_amount,
        'current_amount': start_amount,
        'target': target,
        'days_total': days,
        'start_date': now.strftime('%d/%m/%Y'),
        'day': 1,
        'history': [{
            'day': 0,
            'date': now.strftime('%d/%m/%Y'),
            'bankroll': start_amount,
            'action': 'Challenge started',
            'result': 'N/A'
        }],
        'wins': 0,
        'losses': 0,
        'streak': 0,
        'best_streak': 0,
        'active': True
    }
    _save_challenge(data)
    
    msg = f"🏆 CHALLENGE STARTED\n"
    msg += f"━━━━━━━━━━━━━━━━━\n\n"
    msg += f"💰 Start: ${start_amount:.2f}\n"
    msg += f"🎯 Target: ${target:,.0f}\n"
    msg += f"📅 Days: {days}\n"
    msg += f"📆 Started: {now.strftime('%d/%m/%Y')}\n\n"
    msg += f"Daily growth needed: {((target/start_amount)**(1/days) - 1)*100:.1f}%\n\n"
    msg += f"Let's go 🚀\n"
    msg += f"FlightToProfit ✈️"
    return msg


def update_challenge(bet_amount: float, odds: float, won: bool) -> str:
    """Log a bet in the challenge."""
    data = _load_challenge()
    if not data or not data.get('active'):
        return "❌ No active challenge. Start one with /challenge start <amount> <target> <days>"
    
    now = datetime.now(BEIRUT)
    
    if won:
        profit = bet_amount * (odds - 1)
        data['current_amount'] += profit
        data['wins'] += 1
        data['streak'] = max(0, data['streak']) + 1
        data['best_streak'] = max(data['best_streak'], data['streak'])
        result_icon = '✅'
        result_text = f'WON +${profit:.2f}'
    else:
        data['current_amount'] -= bet_amount
        data['losses'] += 1
        data['streak'] = min(0, data['streak']) - 1
        result_icon = '❌'
        result_text = f'LOST -${bet_amount:.2f}'
    
    data['history'].append({
        'day': data['day'],
        'date': now.strftime('%d/%m/%Y'),
        'bankroll': data['current_amount'],
        'bet': bet_amount,
        'odds': odds,
        'result': 'won' if won else 'lost',
        'action': result_text
    })
    
    # Check if challenge completed or busted
    progress = (data['current_amount'] / data['target']) * 100
    
    if data['current_amount'] >= data['target']:
        data['active'] = False
        _save_challenge(data)
        return _challenge_complete_msg(data)
    
    if data['current_amount'] <= 0:
        data['active'] = False
        _save_challenge(data)
        return f"💀 CHALLENGE BUSTED\n\nBankroll hit $0. Better luck next time.\nFlightToProfit ✈️"
    
    _save_challenge(data)
    
    total = data['wins'] + data['losses']
    wr = (data['wins'] / total * 100) if total > 0 else 0
    
    msg = f"{result_icon} CHALLENGE UPDATE — Day {data['day']}\n"
    msg += f"━━━━━━━━━━━━━━━━━\n\n"
    msg += f"{result_text} (@ {odds:.2f})\n\n"
    msg += f"💰 Bankroll: ${data['current_amount']:.2f}\n"
    msg += f"🎯 Target: ${data['target']:,.0f} ({progress:.1f}%)\n"
    msg += f"📊 Record: {data['wins']}W - {data['losses']}L ({wr:.0f}%)\n"
    
    if data['streak'] > 0:
        msg += f"🔥 Win streak: {data['streak']}"
        if data['streak'] >= 3:
            msg += " 🔥🔥🔥"
        msg += "\n"
    
    msg += f"\n{'█' * int(progress / 5)}{'░' * (20 - int(progress / 5))} {progress:.1f}%\n\n"
    msg += f"FlightToProfit ✈️"
    return msg


def get_challenge_status() -> str:
    """Get current challenge status."""
    data = _load_challenge()
    if not data:
        return "❌ No challenge active.\n\nStart one:\n/challenge start 10 10000 12\n\n(Start $10, target $10K, 12 days)"
    
    if not data.get('active'):
        return "Challenge completed. Start a new one with:\n/challenge start <amount> <target> <days>"
    
    total = data['wins'] + data['losses']
    wr = (data['wins'] / total * 100) if total > 0 else 0
    progress = (data['current_amount'] / data['target']) * 100
    growth = ((data['current_amount'] / data['start_amount']) - 1) * 100
    
    msg = f"🏆 CHALLENGE STATUS — Day {data['day']}\n"
    msg += f"━━━━━━━━━━━━━━━━━\n\n"
    msg += f"💰 Start: ${data['start_amount']:.2f}\n"
    msg += f"💰 Current: ${data['current_amount']:.2f} ({'+' if growth >= 0 else ''}{growth:.0f}%)\n"
    msg += f"🎯 Target: ${data['target']:,.0f}\n\n"
    msg += f"📊 Record: {data['wins']}W - {data['losses']}L ({wr:.0f}%)\n"
    msg += f"🔥 Best Streak: {data['best_streak']}\n\n"
    msg += f"{'█' * int(progress / 5)}{'░' * (20 - int(progress / 5))} {progress:.1f}%\n\n"
    msg += f"FlightToProfit ✈️"
    return msg


def advance_day() -> str:
    """Move to next day."""
    data = _load_challenge()
    if not data or not data.get('active'):
        return "No active challenge."
    data['day'] += 1
    _save_challenge(data)
    return f"📅 Challenge Day {data['day']} started.\n💰 Bankroll: ${data['current_amount']:.2f}"


def _challenge_complete_msg(data: dict) -> str:
    total = data['wins'] + data['losses']
    wr = (data['wins'] / total * 100) if total > 0 else 0
    growth = ((data['current_amount'] / data['start_amount']) - 1) * 100
    
    msg = f"🏆🏆🏆 CHALLENGE COMPLETE 🏆🏆🏆\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"💰 ${data['start_amount']:.2f} → ${data['current_amount']:.2f}\n"
    msg += f"📈 Growth: +{growth:.0f}%\n"
    msg += f"📊 Record: {data['wins']}W - {data['losses']}L ({wr:.0f}%)\n"
    msg += f"🔥 Best Streak: {data['best_streak']}\n"
    msg += f"📅 Days: {data['day']}\n\n"
    msg += f"█████████████████████ 100%\n\n"
    msg += f"Want these picks? Follow @FlightToProfit ✈️"
    return msg
