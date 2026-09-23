"""Formatters v3 — BetArabia style, exact bet labels."""
from data.models import Prediction, Match, Team
import pytz

BEIRUT_TZ = pytz.timezone('Asia/Beirut')

def _to_beirut(dt):
    if dt is None:
        return None
    try:
        if dt.tzinfo:
            return dt.astimezone(BEIRUT_TZ)
        return BEIRUT_TZ.localize(dt)
    except Exception:
        return dt

def _flag(league: str) -> str:
    flags = {
        'mlb': '🇺🇸', 'nba': '🇺🇸', 'usa.1': '🇺🇸',
        'eng.1': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'eng.2': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'esp.1': '🇪🇸', 'ger.1': '🇩🇪',
        'ita.1': '🇮🇹', 'fra.1': '🇫🇷', 'tur.1': '🇹🇷',
        'ned.1': '🇳🇱', 'por.1': '🇵🇹', 'bel.1': '🇧🇪',
        'sco.1': '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'gre.1': '🇬🇷', 'sui.1': '🇨🇭', 'aut.1': '🇦🇹',
        'mex.1': '🇲🇽', 'bra.1': '🇧🇷', 'arg.1': '🇦🇷',
        'ksa.1': '🇸🇦', 'jpn.1': '🇯🇵', 'aus.1': '🇦🇺',
        'uefa.champions': '🇪🇺', 'uefa.europa': '🇪🇺', 'uefa.europa.conf': '🇪🇺'
    }
    return flags.get(league, '🏟️')

def _bet_label(bet_type: str, match: Match) -> tuple:
    """Returns (bet_name, bet_category) matching BetArabia labels."""
    bt = bet_type.upper()
    home = match.home_team.name
    away = match.away_team.name
    
    if bt == 'HOME_WIN':
        return (home, "Full Time Result")
    elif bt == 'AWAY_WIN':
        return (away, "Full Time Result")
    elif bt == 'DRAW':
        return ("Draw", "Full Time Result")
    elif bt == 'HOME_OR_DRAW':
        return (f"{home} or Draw", "Double Chance")
    elif bt == 'AWAY_OR_DRAW':
        return (f"{away} or Draw", "Double Chance")
    elif bt.startswith('OVER_'):
        line = bt.replace('OVER_', '')
        return (f"Over {line}", "Total Goals")
    elif bt.startswith('UNDER_'):
        line = bt.replace('UNDER_', '')
        return (f"Under {line}", "Total Goals")
    elif bt == 'BTTS_YES':
        return ("Yes", "Both Teams to Score")
    elif bt == 'BTTS_NO':
        return ("No", "Both Teams to Score")
    elif bt == 'CLEAN_SHEET_HOME':
        return (f"{home} Clean Sheet", "Clean Sheet")
    elif bt == 'CLEAN_SHEET_AWAY':
        return (f"{away} Clean Sheet", "Clean Sheet")
    elif bt == 'HOME_WIN_TO_NIL':
        return (f"{home} Win to Nil", "Win to Nil")
    elif bt == 'AWAY_WIN_TO_NIL':
        return (f"{away} Win to Nil", "Win to Nil")
    elif bt == 'HOME_-1.5':
        return (f"{home} -1.5", "Handicap")
    elif bt == 'AWAY_+1.5':
        return (f"{away} +1.5", "Handicap")
    elif bt == 'HOME_OVER_0.5':
        return (f"{home} Over 0.5", "Team Goals")
    elif bt == 'AWAY_OVER_0.5':
        return (f"{away} Over 0.5", "Team Goals")
    elif bt == 'HOME_OVER_1.5':
        return (f"{home} Over 1.5", "Team Goals")
    elif bt == 'AWAY_OVER_1.5':
        return (f"{away} Over 1.5", "Team Goals")
    return (bt, "Bet")

def format_prediction(prediction: Prediction) -> str:
    """Single pick with signals, stars, storyline, weather."""
    match = prediction.match
    flag = _flag(match.league)
    local_time = _to_beirut(match.start_time)
    time_str = local_time.strftime("%d/%m/%Y, %I:%M %p") if local_time else "TBD"
    
    bet_name, bet_category = _bet_label(prediction.recommended_bet, match)
    conf = f"{prediction.confidence*100:.0f}%"
    
    # Star rating from signal stack
    stars = prediction.analysis.get('star_count', 0)
    star_str = '⭐' * stars if stars > 0 else ''
    
    tier_icon = {'FIRE': '🔥', 'SOLID': '💪', 'LEAN': '🎯'}.get(prediction.tier, '📊')
    
    msg = f"  {tier_icon} {bet_name} @ {conf} {star_str}\n"
    msg += f"  {bet_category}\n"
    
    # Secondary bets
    secondary = prediction.analysis.get('secondary_bets', [])
    for sb in secondary:
        sb_name, sb_cat = _bet_label(sb['bet'], match)
        sb_conf = f"{sb['prob']*100:.0f}%"
        msg += f"  ➕ {sb_name} @ {sb_conf} ({sb_cat})\n"
    
    msg += f"\n  {flag} {match.home_team.name}\n"
    msg += f"     {match.away_team.name}\n"
    msg += f"  🕐 {time_str}\n"
    
    # Storyline
    storyline = prediction.analysis.get('storyline', '')
    if storyline:
        msg += f"  {storyline}\n"
    
    # Signal stack summary (show passed signals)
    sig_data = prediction.analysis.get('signal_stack', {})
    signals = sig_data.get('signals', [])
    if signals:
        msg += f"  ✅ {len(signals)}/5 signals passed\n"
    
    # Edge explanation
    edge_reasons = prediction.analysis.get('edge_reasons', [])
    if edge_reasons:
        msg += f"  📊 {edge_reasons[0]}\n"
        for er in edge_reasons[1:]:
            msg += f"  {er}\n"
    
    # Weather
    weather = prediction.analysis.get('weather', {})
    if weather.get('description') and weather['description'] != 'Unknown':
        msg += f"  🌤️ {weather['description']}\n"
    
    return msg

def format_daily_picks(predictions: list, label: str = "TODAY", date_str: str = "") -> str:
    if not predictions:
        header = f"✈️ No strong picks for {label.lower()}."
        if date_str:
            header += f" ({date_str})"
        return f"{header}\n\nFlightToProfit ✈️"
    
    header = f"✈️ {label}'S PICKS ({len(predictions)})"
    if date_str:
        header += f" — {date_str}"
    
    msg = f"{header}\n"
    msg += "━━━━━━━━━━━━━━━━━\n\n"
    
    for p in predictions:
        msg += format_prediction(p)
        msg += "─────────────\n\n"
    
    msg += "💡 3 quality picks > 15 rushed bets\n"
    msg += "⭐ Signal-stacked | Singles only\n"
    msg += "FlightToProfit ✈️"
    return msg

def format_bankroll_stats(stats: dict, bankroll: float) -> str:
    wr = stats['win_rate']
    indicator = "🟢" if wr >= 50 else "🔴"
    msg = f"✈️ STATS\n━━━━━━━━━━━━━━━━━\n\n"
    msg += f"  Balance: ${bankroll:.2f}\n"
    msg += f"  Record: {stats['wins']}W - {stats['losses']}L\n"
    msg += f"  Win Rate: {wr:.0f}% {indicator}\n"
    msg += f"  Profit: ${stats['total_profit']:.2f}\n\n"
    msg += "FlightToProfit ✈️"
    return msg

def format_team_form(team: Team, form_data: dict) -> str:
    form_str = ''.join(team.recent_form[-5:]) if team.recent_form else 'N/A'
    msg = f"✈️ {team.name}\n━━━━━━━━━━━━━━━━━\n\n"
    msg += f"  Form: {form_str}\n"
    msg += f"  Avg Scored: {form_data.get('avg_scored', 0):.1f}\n"
    msg += f"  Avg Conceded: {form_data.get('avg_conceded', 0):.1f}\n\n"
    msg += "FlightToProfit ✈️"
    return msg

def format_match_list(matches: list) -> str:
    if not matches:
        return "No upcoming matches.\n\nFlightToProfit ✈️"
    msg = "✈️ UPCOMING\n━━━━━━━━━━━━━━━━━\n\n"
    grouped = {}
    for m in matches:
        key = f"{_flag(m.league)} {m.league.upper()}"
        grouped.setdefault(key, []).append(m)
    for group, m_list in grouped.items():
        msg += f"{group}\n"
        for m in m_list:
            local_time = _to_beirut(m.start_time)
            time_str = local_time.strftime("%b %d, %I:%M %p") if local_time else "TBD"
            msg += f"  {m.home_team.abbreviation} vs {m.away_team.abbreviation} • {time_str}\n"
        msg += "\n"
    msg += "FlightToProfit ✈️"
    return msg
