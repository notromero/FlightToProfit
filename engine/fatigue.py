"""
Fatigue Detection — back-to-back games, travel, schedule density.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

TIMEZONE_MAP = {
    # ET teams
    'yankees': 'ET', 'mets': 'ET', 'red sox': 'ET', 'phillies': 'ET',
    'nationals': 'ET', 'orioles': 'ET', 'rays': 'ET', 'marlins': 'ET',
    'braves': 'ET', 'pirates': 'ET', 'blue jays': 'ET', 'guardians': 'ET',
    'tigers': 'ET', 'reds': 'ET',
    # CT teams
    'cubs': 'CT', 'white sox': 'CT', 'brewers': 'CT', 'cardinals': 'CT',
    'twins': 'CT', 'royals': 'CT', 'rangers': 'CT', 'astros': 'CT',
    # MT teams
    'rockies': 'MT', 'diamondbacks': 'MT',
    # PT teams
    'dodgers': 'PT', 'angels': 'PT', 'padres': 'PT', 'giants': 'PT',
    'athletics': 'PT', 'mariners': 'PT',
}

TZ_DIFF = {'ET': 0, 'CT': 1, 'MT': 2, 'PT': 3}


class FatigueAnalyzer:
    def check_fatigue(self, team_name: str, sport: str, schedule: list = None) -> dict:
        """
        Check fatigue based on recent games.
        schedule: list of recent game dates as strings (YYYY-MM-DD) or datetimes
        """
        defaults = {
            'fatigue_level': 'FRESH', 'adjustment': 0,
            'reason': '', 'games_last_3_days': 0, 'is_back_to_back': False
        }
        
        if not schedule:
            return defaults
        
        try:
            today = datetime.utcnow().date()
            recent_dates = []
            for d in schedule:
                if isinstance(d, str):
                    try:
                        dt = datetime.strptime(d[:10], '%Y-%m-%d').date()
                    except ValueError:
                        continue
                elif hasattr(d, 'date'):
                    dt = d.date() if hasattr(d, 'date') else d
                else:
                    continue
                recent_dates.append(dt)
            
            recent_dates.sort(reverse=True)
            
            # Count games in last 3 days
            days_3 = sum(1 for d in recent_dates if (today - d).days <= 3 and (today - d).days > 0)
            
            # Back-to-back: played yesterday
            yesterday = today - timedelta(days=1)
            day_before = today - timedelta(days=2)
            
            played_yesterday = yesterday in recent_dates
            played_day_before = day_before in recent_dates
            
            is_b2b = played_yesterday
            
            is_baseball = sport.lower() in ('baseball', 'mlb')
            is_soccer = sport.lower() in ('soccer', 'football')
            
            if days_3 >= 3:
                return {
                    'fatigue_level': 'EXHAUSTED', 'adjustment': -8,
                    'reason': f'{days_3} games in 3 days',
                    'games_last_3_days': days_3, 'is_back_to_back': is_b2b
                }
            
            if is_baseball:
                if played_yesterday and played_day_before:
                    return {
                        'fatigue_level': 'TIRED', 'adjustment': -5,
                        'reason': 'Back-to-back-to-back games',
                        'games_last_3_days': days_3, 'is_back_to_back': True
                    }
                elif played_yesterday:
                    return {
                        'fatigue_level': 'NORMAL', 'adjustment': -2,
                        'reason': 'Played yesterday',
                        'games_last_3_days': days_3, 'is_back_to_back': True
                    }
            
            if is_soccer:
                # Check for midweek game (Tue-Thu) before weekend
                today_dow = today.weekday()  # 0=Mon
                if today_dow in (5, 6):  # Sat/Sun
                    midweek = [d for d in recent_dates 
                               if d.weekday() in (1, 2, 3) and 0 < (today - d).days <= 5]
                    if midweek:
                        return {
                            'fatigue_level': 'TIRED', 'adjustment': -5,
                            'reason': 'Midweek match before weekend',
                            'games_last_3_days': days_3, 'is_back_to_back': False
                        }
                # Played 3 days ago
                three_days_ago = today - timedelta(days=3)
                if three_days_ago in recent_dates:
                    return {
                        'fatigue_level': 'NORMAL', 'adjustment': -2,
                        'reason': 'Short rest (3 days)',
                        'games_last_3_days': days_3, 'is_back_to_back': False
                    }
            
            return defaults
        except Exception as e:
            logger.debug(f"Fatigue check error: {e}")
            return defaults

    def check_travel(self, home_team: str, away_team: str) -> dict:
        """Check timezone-based travel penalty."""
        try:
            home_tz = self._get_tz(home_team)
            away_tz = self._get_tz(away_team)
            
            if not home_tz or not away_tz:
                return {'away_travel_penalty': -1, 'note': 'Away game'}
            
            tz_gap = abs(TZ_DIFF.get(home_tz, 0) - TZ_DIFF.get(away_tz, 0))
            
            if tz_gap >= 3:
                return {'away_travel_penalty': -3, 'note': f'Cross-country travel ({away_tz}→{home_tz})'}
            elif tz_gap >= 2:
                return {'away_travel_penalty': -2, 'note': f'Long travel ({away_tz}→{home_tz})'}
            else:
                return {'away_travel_penalty': -1, 'note': 'Away game'}
        except Exception:
            return {'away_travel_penalty': -1, 'note': 'Away game'}

    def _get_tz(self, team_name: str) -> Optional[str]:
        name = team_name.lower()
        for key, tz in TIMEZONE_MAP.items():
            if key in name:
                return tz
        return None

    @staticmethod
    def get_fatigue_summary(fatigue: dict) -> str:
        level = fatigue.get('fatigue_level', 'FRESH')
        reason = fatigue.get('reason', '')
        if level == 'EXHAUSTED':
            return f'🥱 Heavy fatigue: {reason}'
        elif level == 'TIRED':
            return f'😴 Fatigued: {reason}'
        return ''
