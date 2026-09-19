"""
Signal Stack — Masked Bettor method.
Every soccer pick must pass 5 signals before it earns conviction stars.
Picks with < 3 stars get killed. Only 3-5 star picks survive.

SIGNALS:
1. HOME FORM ISOLATION — only home record matters for home picks, only away for away
2. AWAY FORM VETO — if the away team has 3+ away wins in last 5, veto home pick
3. GIANT-KILLER BOUNCE — teams that just beat a top-4 side often drop the next game
4. GOALKEEPER CHECK — clean sheets in last 5 games (defensive solidity)
5. SMART MONEY — if our model agrees with the line movement direction

DRAW TRAP — desperate teams at home DON'T draw. Kill draw bets on:
- Bottom 5 teams playing at home
- Teams on 3+ game losing streaks at home
- Teams who NEED points for survival

STORYLINE METHOD — read the league table context:
- Relegation fights = desperate = more goals, fewer draws
- Title races = tight = fewer goals, more draws
- Mid-table nothing-to-play-for = unpredictable = avoid
"""
import logging
from typing import Dict, List, Optional, Any
from data.models import Match, Team, Prediction

logger = logging.getLogger(__name__)


class SignalStack:
    """Scores picks 0-5 stars based on the 5-signal system."""

    def score_pick(self, match: Match, prediction: Prediction) -> dict:
        """
        Run all 5 signals + draw trap + storyline on a pick.
        Returns dict with star_count, signals (list of passed), 
        vetoes (list of failed), storyline, and draw_trap flag.
        """
        home = match.home_team
        away = match.away_team
        bet = prediction.recommended_bet
        is_soccer = match.sport.lower() in ('soccer', 'football')
        
        signals = []
        vetoes = []
        star_count = 0
        storyline = ''
        draw_trap = False

        if not is_soccer:
            # Non-soccer: auto 3 stars if FIRE/SOLID tier
            return {
                'star_count': 3 if prediction.tier in ('FIRE', 'SOLID') else 1,
                'signals': ['Non-soccer: tier-based'],
                'vetoes': [],
                'storyline': '',
                'draw_trap': False
            }

        # === SIGNAL 1: HOME FORM ISOLATION ===
        sig1 = self._signal_home_form(home, away, bet)
        if sig1['passed']:
            signals.append(sig1['reason'])
            star_count += 1
        else:
            vetoes.append(sig1['reason'])

        # === SIGNAL 2: AWAY FORM VETO ===
        sig2 = self._signal_away_veto(home, away, bet)
        if sig2['passed']:
            signals.append(sig2['reason'])
            star_count += 1
        else:
            vetoes.append(sig2['reason'])

        # === SIGNAL 3: GIANT-KILLER BOUNCE ===
        sig3 = self._signal_giant_killer(home, away, bet)
        if sig3['passed']:
            signals.append(sig3['reason'])
            star_count += 1
        else:
            vetoes.append(sig3['reason'])

        # === SIGNAL 4: GOALKEEPER / CLEAN SHEET CHECK ===
        sig4 = self._signal_goalkeeper(home, away, bet)
        if sig4['passed']:
            signals.append(sig4['reason'])
            star_count += 1
        else:
            vetoes.append(sig4['reason'])

        # === SIGNAL 5: MODEL CONFIDENCE (smart money proxy) ===
        sig5 = self._signal_model_confidence(prediction)
        if sig5['passed']:
            signals.append(sig5['reason'])
            star_count += 1
        else:
            vetoes.append(sig5['reason'])

        # === DRAW TRAP ===
        draw_trap = self._check_draw_trap(home, away, bet)

        # === STORYLINE ===
        storyline = self._read_storyline(home, away, match)

        return {
            'star_count': star_count,
            'signals': signals,
            'vetoes': vetoes,
            'storyline': storyline,
            'draw_trap': draw_trap
        }

    def _signal_home_form(self, home: Team, away: Team, bet: str) -> dict:
        """Signal 1: Home form for home picks, away form for away picks."""
        if 'HOME' in bet or 'HOME_OR_DRAW' in bet:
            # Check home team's HOME record specifically
            hw, hl, hd = home.home_record
            total = hw + hl + hd
            if total >= 3:
                win_pct = hw / total
                if win_pct >= 0.55:
                    return {'passed': True, 'reason': f'🏠 Home form {hw}W-{hl}L ({win_pct:.0%})'}
                else:
                    return {'passed': False, 'reason': f'🏠 Weak home form {hw}W-{hl}L ({win_pct:.0%})'}
            # Not enough data — pass with note
            return {'passed': True, 'reason': '🏠 Home form: limited data'}
        
        elif 'AWAY' in bet:
            aw, al, ad = away.away_record
            total = aw + al + ad
            if total >= 3:
                win_pct = aw / total
                if win_pct >= 0.40:
                    return {'passed': True, 'reason': f'✈️ Away form {aw}W-{al}L ({win_pct:.0%})'}
                else:
                    return {'passed': False, 'reason': f'✈️ Weak away form {aw}W-{al}L ({win_pct:.0%})'}
            return {'passed': True, 'reason': '✈️ Away form: limited data'}
        
        # For non-winner bets (O/U, BTTS) — auto pass
        return {'passed': True, 'reason': '📊 Market bet: form N/A'}

    def _signal_away_veto(self, home: Team, away: Team, bet: str) -> dict:
        """Signal 2: If away team is strong away, veto home pick."""
        if 'HOME' not in bet:
            return {'passed': True, 'reason': '✓ Not a home pick'}
        
        aw, al, ad = away.away_record
        total = aw + al + ad
        if total >= 3:
            away_win_pct = aw / total
            if away_win_pct >= 0.60:
                return {'passed': False, 'reason': f'⚠️ Away team strong on road ({aw}W in {total} away)'}
        
        # Also check away team's recent form
        if away.recent_form:
            last5 = away.recent_form[-5:]
            away_wins = last5.count('W')
            if away_wins >= 4:
                return {'passed': False, 'reason': f'⚠️ Away team on fire ({away_wins}W in last 5)'}
        
        return {'passed': True, 'reason': '✓ Away team not dangerous on road'}

    def _signal_giant_killer(self, home: Team, away: Team, bet: str) -> dict:
        """Signal 3: Teams that just beat a top side often drop next game."""
        # Check if the team we're betting ON just had a big upset win
        # (indicated by beating a significantly higher-rated team)
        # We approximate this by checking if last result was W after losses
        
        if not home.recent_form or not away.recent_form:
            return {'passed': True, 'reason': '✓ No giant-killer bounce detected'}
        
        # The team we're backing
        if 'HOME' in bet:
            form = home.recent_form
        elif 'AWAY' in bet:
            form = away.recent_form
        else:
            return {'passed': True, 'reason': '✓ Market bet: bounce N/A'}
        
        if len(form) >= 3:
            # Pattern: L, L, W — could be giant-killer bounce (win was fluke)
            last3 = form[-3:]
            if last3 == ['L', 'L', 'W']:
                return {'passed': False, 'reason': '⚡ Giant-killer bounce risk (LLW pattern)'}
            # Pattern: L, W, W after long losing streak could be genuine turnaround
            if last3 == ['L', 'W', 'W']:
                return {'passed': True, 'reason': '✓ Genuine form recovery (LWW)'}
        
        return {'passed': True, 'reason': '✓ No bounce risk'}

    def _signal_goalkeeper(self, home: Team, away: Team, bet: str) -> dict:
        """Signal 4: Defensive solidity — clean sheets in recent games."""
        if 'HOME' in bet or 'HOME_OR_DRAW' in bet:
            team = home
            label = 'Home'
        elif 'AWAY' in bet:
            team = away
            label = 'Away'
        else:
            return {'passed': True, 'reason': '✓ Market bet: GK N/A'}
        
        if team.goals_conceded_last_n:
            last5 = team.goals_conceded_last_n[-5:]
            clean_sheets = sum(1 for g in last5 if g == 0)
            avg_conceded = sum(last5) / len(last5)
            
            if clean_sheets >= 2:
                return {'passed': True, 'reason': f'🧤 {label} solid defense ({clean_sheets} CS in {len(last5)})'}
            elif avg_conceded <= 1.0:
                return {'passed': True, 'reason': f'🧤 {label} low conceding ({avg_conceded:.1f}/game)'}
            elif avg_conceded >= 2.0:
                return {'passed': False, 'reason': f'🧤 {label} leaky defense ({avg_conceded:.1f}/game)'}
        
        return {'passed': True, 'reason': '🧤 Defensive data limited'}

    def _signal_model_confidence(self, prediction: Prediction) -> dict:
        """Signal 5: Our model's conviction (proxy for smart money)."""
        conf = prediction.confidence
        if conf >= 0.80:
            return {'passed': True, 'reason': f'📈 High conviction ({conf:.0%})'}
        elif conf >= 0.65:
            return {'passed': True, 'reason': f'📈 Good conviction ({conf:.0%})'}
        elif conf >= 0.55:
            return {'passed': False, 'reason': f'📉 Weak conviction ({conf:.0%})'}
        else:
            return {'passed': False, 'reason': f'📉 Low conviction ({conf:.0%})'}

    def _check_draw_trap(self, home: Team, away: Team, bet: str) -> bool:
        """
        DRAW TRAP: Desperate teams at home DON'T draw.
        If we're betting draw on a desperate home team, it's a trap.
        """
        if 'DRAW' not in bet and 'HOME_OR_DRAW' not in bet:
            return False
        
        hw, hl, hd = home.home_record
        total = hw + hl + hd
        
        # Desperate = bad home record + losing form
        if total >= 3:
            home_win_pct = hw / total
            if home_win_pct <= 0.30:
                # Desperate team — they'll push for the win, not settle for draw
                return True
        
        # Check losing streak
        if home.recent_form:
            last3 = home.recent_form[-3:]
            if last3.count('L') >= 3:
                return True  # 3 straight losses = desperate
        
        return False

    def _read_storyline(self, home: Team, away: Team, match: Match) -> str:
        """
        STORYLINE METHOD: Read the league table context.
        What's at stake for each team?
        """
        hw, hl, hd = home.overall_record
        aw, al, ad = away.overall_record
        
        h_total = hw + hl + hd
        a_total = aw + al + ad
        
        if h_total < 5 or a_total < 5:
            return ''
        
        h_pct = hw / h_total if h_total > 0 else 0.5
        a_pct = aw / a_total if a_total > 0 else 0.5
        
        stories = []
        
        # Bottom team fighting (desperation = more goals)
        if h_pct <= 0.30:
            stories.append(f'📖 {home.name} in relegation zone — desperate for points')
        if a_pct <= 0.30:
            stories.append(f'📖 {away.name} in relegation zone — desperate for points')
        
        # Top team cruising
        if h_pct >= 0.70:
            stories.append(f'📖 {home.name} near top — confident at home')
        if a_pct >= 0.70:
            stories.append(f'📖 {away.name} near top — dangerous on road')
        
        # Mid-table clash (unpredictable)
        if 0.35 <= h_pct <= 0.55 and 0.35 <= a_pct <= 0.55:
            stories.append('📖 Mid-table clash — unpredictable, tread carefully')
        
        # Mismatch storyline
        if abs(h_pct - a_pct) >= 0.30:
            better = home.name if h_pct > a_pct else away.name
            stories.append(f'📖 Clear quality gap — {better} should dominate')
        
        return ' | '.join(stories) if stories else ''

    def filter_predictions(self, predictions: List[Prediction], 
                           matches_map: Dict[str, Match],
                           min_stars: int = 3) -> List[Prediction]:
        """
        Run signal stack on all predictions.
        Kill anything under min_stars. Max 3 picks (quality over quantity).
        """
        scored = []
        for pred in predictions:
            match = pred.match
            result = self.score_pick(match, pred)
            
            # Kill draw traps
            if result['draw_trap']:
                logger.info(f"Draw trap killed: {match.home_team.name} vs {match.away_team.name}")
                continue
            
            # Add signal data to analysis
            pred.analysis['signal_stack'] = result
            pred.analysis['star_count'] = result['star_count']
            pred.analysis['storyline'] = result['storyline']
            
            if result['star_count'] >= min_stars:
                scored.append(pred)
        
        # Sort by stars first, then confidence
        scored.sort(key=lambda p: (p.analysis.get('star_count', 0), p.confidence), reverse=True)
        
        # MAX 3 picks — quality over quantity (Masked Bettor rule)
        return scored[:3]
