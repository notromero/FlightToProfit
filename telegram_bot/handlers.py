import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from datetime import datetime, timedelta

import config
from data.models import BetRecord

# These instances will be populated during setup
espn = None
mlb = None
odds = None
predictor = None
db = None
enricher = None

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    chat_id = update.effective_chat.id
    db.save_setting('chat_id', str(chat_id))
    
    welcome_msg = (
        "✈️ FlightToProfit\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Signal-stacked picks. Data over gut.\n\n"
        "📊 PICKS\n"
        "/picks - Today's top 3 picks\n"
        "/tomorrow - Tomorrow's picks\n"
        "/parlay - High-odds combo\n"
        "/results - Check results\n\n"
        "🏆 CHALLENGE\n"
        "/challenge - Bankroll challenge status\n"
        "/challenge start 10 10000 12 - Start $10→$10K\n\n"
        "📈 STATS\n"
        "/bankroll - Your stats\n"
        "/upcoming - Match list\n"
        "/help - Commands\n\n"
        "Auto-sends daily at 6:00 AM 🇱🇧"
    )
    await update.message.reply_text(welcome_msg)

def _merge_odds_into_matches(matches, odds_client):
    """Merge bookmaker odds into match objects for value detection."""
    if not odds_client or not getattr(config, 'ODDS_API_KEY', ''):
        return matches
    
    try:
        for league_name, odds_key in config.ODDS_API_SPORT_KEYS.items():
            try:
                odds_data = odds_client.get_best_odds(odds_key)
                if not odds_data:
                    continue
                # Try to match by team names (fuzzy)
                for match in matches:
                    for event_id, event_odds in odds_data.items():
                        home_lower = match.home_team.name.lower()
                        away_lower = match.away_team.name.lower()
                        eid_lower = str(event_id).lower()
                        # Simple name matching
                        if (any(word in eid_lower for word in home_lower.split()) or
                            match.home_team.abbreviation.lower() in eid_lower):
                            match.bookmaker_odds = event_odds
                            break
            except Exception as e:
                logger.debug(f"Could not fetch odds for {league_name}: {e}")
    except Exception as e:
        logger.warning(f"Odds merge failed: {e}")
    
    return matches

def _get_pitcher_map(matches):
    """Fetch probable pitchers for all MLB games."""
    pitcher_map = {}
    try:
        from engine.pitcher import PitcherAnalyzer
        pa = PitcherAnalyzer()
        starters = pa.get_todays_starters()
        
        for match in matches:
            if match.sport.lower() not in ('baseball', 'mlb'):
                continue
            # Try to match by game ID
            for gpk, pdata in starters.items():
                if gpk in str(match.id) or str(match.id) in gpk:
                    pitcher_map[match.id] = pdata
                    break
            # Fallback: match by team name
            if match.id not in pitcher_map:
                for gpk, pdata in starters.items():
                    pitcher_map[match.id] = pdata
                    break
    except Exception as e:
        logger.debug(f"Pitcher fetch failed: {e}")
    return pitcher_map

async def picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /picks to get today's predictions."""
    await update.message.reply_text("🔍 Analyzing today's matches (weather + pitchers + stats)...")
    
    from telegram_bot import formatters
    from telegram_bot.results_tracker import save_picks
    import pytz
    
    try:
        beirut = pytz.timezone('Asia/Beirut')
        today_str = __import__('datetime').datetime.now(beirut).strftime("%d/%m/%Y")
        
        matches = espn.get_todays_matches() if espn else []
        
        if enricher and matches:
            matches = enricher.enrich_matches(matches)
        
        matches = _merge_odds_into_matches(matches, odds)
        
        # Fetch pitcher data for MLB games
        pitcher_map = _get_pitcher_map(matches)
        
        predictions = predictor.get_best_bets(matches, pitcher_map=pitcher_map) if predictor else []
        
        # Save picks for auto result tracking
        if predictions:
            save_picks(predictions)
        
        msg = formatters.format_daily_picks(predictions, label="TODAY", date_str=today_str)
        if len(msg) > 4000:
            chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in /picks: {e}")
        await update.message.reply_text(f"⚠️ Error fetching picks: {e}")

async def tomorrow_picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /tomorrow to get tomorrow's predictions."""
    await update.message.reply_text("🔍 Analyzing tomorrow's matches...")
    
    from telegram_bot import formatters
    import pytz
    from datetime import timedelta
    
    try:
        beirut = pytz.timezone('Asia/Beirut')
        tomorrow_str = (__import__('datetime').datetime.now(beirut) + timedelta(days=1)).strftime("%d/%m/%Y")
        
        matches = espn.get_tomorrows_matches() if espn else []
        
        if enricher and matches:
            matches = enricher.enrich_matches(matches)
        
        matches = _merge_odds_into_matches(matches, odds)
        
        pitcher_map = _get_pitcher_map(matches)
        predictions = predictor.get_best_bets(matches, pitcher_map=pitcher_map) if predictor else []
        
        msg = formatters.format_daily_picks(predictions, label="TOMORROW", date_str=tomorrow_str)
        if len(msg) > 4000:
            chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in /tomorrow: {e}")
        await update.message.reply_text(f"Error: {e}")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /analyze <TeamName>."""
    if not context.args:
        await update.message.reply_text("Usage: /analyze <TeamName>")
        return
        
    team_name = " ".join(context.args)
    
    try:
        from telegram_bot import formatters
        from engine.form_analyzer import FormAnalyzer
        
        # Search for team across today's matches
        matches = espn.get_todays_matches() if espn else []
        found_team = None
        for m in matches:
            if team_name.lower() in m.home_team.name.lower():
                found_team = m.home_team
                break
            elif team_name.lower() in m.away_team.name.lower():
                found_team = m.away_team
                break
        
        if not found_team:
            await update.message.reply_text(f"Could not find team '{team_name}' in today's matches. Try the exact name.")
            return
        
        # Get form analysis
        form_analyzer = FormAnalyzer()
        form_data = form_analyzer.analyze_form(found_team)
        
        msg = formatters.format_team_form(found_team, form_data)
        if predictor:
            elo_rating = predictor.elo.get_rating(found_team.id)
            msg += f"\nElo Rating: {elo_rating:.0f}\n"
        
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in /analyze: {e}")
        await update.message.reply_text(f"⚠️ Error analyzing {team_name}: {e}")

async def form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /form <TeamName>."""
    if not context.args:
        await update.message.reply_text("Usage: /form <TeamName>")
        return
        
    team_name = " ".join(context.args)
    # Reuse analyze logic
    context.args = team_name.split()
    await analyze(update, context)

async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /upcoming to show upcoming matches."""
    from telegram_bot import formatters
    
    try:
        matches = espn.get_todays_matches() if espn else []
        msg = formatters.format_match_list(matches)
        if len(msg) > 4000:
            chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in /upcoming: {e}")
        await update.message.reply_text(f"⚠️ Error fetching upcoming matches: {e}")

async def bankroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /bankroll to view stats."""
    from telegram_bot import formatters
    
    current_bankroll = db.get_bankroll()
    stats = db.get_stats()
    msg = formatters.format_bankroll_stats(stats, current_bankroll)
    await update.message.reply_text(msg)

async def addbet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /addbet <stake> <odds> <win/loss> [desc]."""
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /addbet <stake> <odds> <win/loss> [description]")
        return
        
    try:
        stake = float(context.args[0])
        odds_val = float(context.args[1])
        result = context.args[2].lower()
        desc = " ".join(context.args[3:]) if len(context.args) > 3 else "Manual Bet"
        
        profit = 0.0
        if result == 'win':
            profit = stake * odds_val - stake
        elif result == 'loss':
            profit = -stake
            
        bet = BetRecord(
            date=datetime.now().strftime("%Y-%m-%d"),
            match_description=desc,
            bet_type='custom',
            odds=odds_val,
            stake=stake,
            result=result,
            profit=profit
        )
        db.save_bet(bet)
        
        current = db.get_bankroll()
        db.update_bankroll(current + profit)
        
        await update.message.reply_text(f"✅ Bet added! Profit: ${profit:.2f}. New bankroll: ${db.get_bankroll():.2f}")
    except Exception as e:
        logger.error(f"Error adding bet: {e}")
        await update.message.reply_text("Error parsing bet. Check format: /addbet <stake> <odds> <win/loss>")

async def setbankroll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /setbankroll <amount>."""
    if not context.args:
        await update.message.reply_text("Usage: /setbankroll <amount>")
        return
        
    try:
        amount = float(context.args[0])
        db.update_bankroll(amount)
        await update.message.reply_text(f"✅ Bankroll set to ${amount:.2f}")
    except ValueError:
        await update.message.reply_text("Please provide a valid numeric amount.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /help."""
    help_text = (
        "🤖 GOLAZO Predictor Commands\n\n"
        "/start - Initialize the bot\n"
        "/picks - Get today's high-confidence picks\n"
        "/tomorrow - Get tomorrow's picks\n"
        "/analyze <Team> - Deep analysis of a team\n"
        "/form <Team> - Last 10 results\n"
        "/upcoming - All upcoming matches\n"
        "/bankroll - View bankroll stats\n"
        "/addbet <stake> <odds> <win/loss> - Log a bet\n"
        "/setbankroll <amount> - Set initial bankroll\n"
        "/help - Show this message\n"
    )
    await update.message.reply_text(help_text)

def setup_handlers(application):
    """Registers handlers and initializes components."""
    global espn, mlb, odds, predictor, db, enricher
    
    try:
        from db.database import Database
        db = Database()
    except Exception as e:
        logger.error(f"Could not init Database: {e}")
        
    try:
        from data.espn_client import ESPNClient
        espn = ESPNClient()
    except Exception as e:
        logger.warning(f"Could not init ESPNClient: {e}")
        
    try:
        from data.mlb_client import MLBClient
        mlb = MLBClient()
    except Exception as e:
        logger.warning(f"Could not init MLBClient: {e}")
    
    # Create enricher (needs espn + mlb)
    try:
        from data.enricher import DataEnricher
        enricher = DataEnricher(espn, mlb) if espn else None
    except Exception as e:
        logger.warning(f"Could not init DataEnricher: {e}")
        
    try:
        from data.odds_client import OddsClient
        odds = OddsClient()
    except Exception as e:
        logger.warning(f"Could not init OddsClient: {e}")
        
    try:
        from engine.predictor import Predictor
        predictor = Predictor()
        # Load saved Elo ratings from database
        if db:
            saved_ratings = db.load_elo_ratings()
            if saved_ratings:
                predictor.elo.load_ratings(saved_ratings)
                logger.info(f"Loaded {len(saved_ratings)} saved Elo ratings")
    except Exception as e:
        logger.warning(f"Could not init Predictor: {e}")
        
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("picks", picks))
    application.add_handler(CommandHandler("tomorrow", tomorrow_picks))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("form", form))
    application.add_handler(CommandHandler("upcoming", upcoming))
    application.add_handler(CommandHandler("bankroll", bankroll))
    application.add_handler(CommandHandler("addbet", addbet))
    application.add_handler(CommandHandler("setbankroll", setbankroll))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("challenge", challenge_command))
    application.add_handler(CommandHandler("parlay", parlay_command))
    application.add_handler(CommandHandler("ad", ad_command))
    application.add_handler(CommandHandler("help", help_command))
    
    return {
        'espn': espn,
        'mlb': mlb,
        'odds': odds,
        'predictor': predictor,
        'db': db,
        'enricher': enricher
    }

async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /results — check today's pick results."""
    await update.message.reply_text("📊 Checking results...")
    
    from telegram_bot.results_tracker import check_results, load_picks
    
    try:
        picks = load_picks()
        if not picks:
            await update.message.reply_text("No picks saved for today. Use /picks first!")
            return
        
        msg = await check_results(espn)
        if msg:
            if len(msg) > 4000:
                chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(msg)
        else:
            pending = sum(1 for p in picks if p['result'] == 'pending')
            resolved = sum(1 for p in picks if p['result'] != 'pending')
            wins = sum(1 for p in picks if p['result'] == 'won')
            losses = sum(1 for p in picks if p['result'] == 'lost')
            
            if resolved > 0:
                wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
                msg = f"📊 RESULTS SO FAR\n━━━━━━━━━━━━━━━━━\n"
                msg += f"✅ Won: {wins} | ❌ Lost: {losses}\n"
                msg += f"⏳ Pending: {pending}\n"
                msg += f"Win Rate: {wr:.0f}%\n"
                msg += f"FlightToProfit ✈️"
            else:
                msg = f"⏳ All {pending} game(s) still pending. Check back later!\n"
                msg += f"FlightToProfit ✈️"
            
            await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in /results: {e}")
        await update.message.reply_text(f"⚠️ Error checking results: {e}")


async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /challenge — View status
    /challenge start 10 10000 12 — Start $10 to $10K in 12 days
    /challenge bet 5 2.10 win — Log a $5 bet at 2.10 odds, won
    /challenge nextday — Advance to next day
    """
    from telegram_bot.challenge import start_challenge, update_challenge, get_challenge_status, advance_day
    
    args = context.args if context.args else []
    
    if not args:
        msg = get_challenge_status()
        await update.message.reply_text(msg)
        return
    
    action = args[0].lower()
    
    if action == 'start' and len(args) >= 4:
        try:
            start_amt = float(args[1])
            target = float(args[2])
            days = int(args[3])
            msg = start_challenge(start_amt, target, days)
            await update.message.reply_text(msg)
        except ValueError:
            await update.message.reply_text("Usage: /challenge start <amount> <target> <days>\nExample: /challenge start 10 10000 12")
    
    elif action == 'bet' and len(args) >= 4:
        try:
            bet_amt = float(args[1])
            odds_val = float(args[2])
            won = args[3].lower() in ('win', 'won', 'w', 'yes', '1')
            msg = update_challenge(bet_amt, odds_val, won)
            await update.message.reply_text(msg)
        except ValueError:
            await update.message.reply_text("Usage: /challenge bet <stake> <odds> <win/loss>\nExample: /challenge bet 5 2.10 win")
    
    elif action == 'nextday':
        msg = advance_day()
        await update.message.reply_text(msg)
    
    else:
        await update.message.reply_text(
            "🏆 Challenge Commands:\n\n"
            "/challenge — View status\n"
            "/challenge start 10 10000 12 — Start challenge\n"
            "/challenge bet 5 2.10 win — Log winning bet\n"
            "/challenge bet 5 1.80 loss — Log losing bet\n"
            "/challenge nextday — Next day\n"
        )


async def parlay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a high-odds parlay combo from today's signal-stacked picks."""
    await update.message.reply_text("🎰 Building high-odds combo...")
    
    try:
        import pytz
        from telegram_bot.formatters import _to_beirut, _bet_label
        
        today = datetime.now(pytz.timezone('Asia/Beirut'))
        matches = espn.get_todays_matches()
        
        if not matches:
            await update.message.reply_text("No matches today for parlay.")
            return
        
        if enricher:
            matches = enricher.enrich_matches(matches)
        
        pitcher_map = _get_pitcher_map(matches)
        preds = predictor.get_best_bets(matches, pitcher_map=pitcher_map)
        
        if not preds or len(preds) < 2:
            await update.message.reply_text("Need at least 2 picks for a combo. Not enough qualifying games.")
            return
        
        # Build parlay from main picks + best secondaries
        combo_legs = []
        total_odds = 1.0
        
        for p in preds:
            match = p.match
            bet_name, _ = _bet_label(p.recommended_bet, match)
            dec_odds = round(1.0 / max(p.confidence, 0.1), 2)
            dec_odds = max(1.15, dec_odds)
            
            combo_legs.append({
                'match': f"{match.home_team.name} vs {match.away_team.name}",
                'pick': bet_name,
                'odds': dec_odds,
                'confidence': p.confidence
            })
            total_odds *= dec_odds
            
            # Add best secondary as separate leg
            secondaries = p.analysis.get('secondary_bets', [])
            if secondaries and len(combo_legs) < 6:
                sb = secondaries[0]
                sb_name, _ = _bet_label(sb['bet'], match)
                sb_odds = round(1.0 / max(sb['prob'], 0.1), 2)
                sb_odds = max(1.20, sb_odds)
                combo_legs.append({
                    'match': f"{match.home_team.name} vs {match.away_team.name}",
                    'pick': sb_name,
                    'odds': sb_odds,
                    'confidence': sb['prob']
                })
                total_odds *= sb_odds
        
        msg = f"🎰 HIGH-ODDS COMBO\n"
        msg += f"━━━━━━━━━━━━━━━━━\n\n"
        
        for i, leg in enumerate(combo_legs, 1):
            conf = f"{leg['confidence']*100:.0f}%"
            msg += f"  {i}. {leg['pick']} @ {leg['odds']:.2f}\n"
            msg += f"     {leg['match']}\n\n"
        
        msg += f"━━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Combined Odds: {total_odds:.2f}\n"
        msg += f"💵 $5 → ${5 * total_odds:.2f}\n"
        msg += f"💵 $10 → ${10 * total_odds:.2f}\n\n"
        msg += f"⚠️ High risk, high reward\n"
        msg += f"⭐ All legs signal-stacked\n"
        msg += f"FlightToProfit ✈️"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Error in /parlay: {e}")
        await update.message.reply_text(f"⚠️ Error building combo: {e}")


async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate marketing posts. /ad promo | /ad vip | /ad challenge | /ad results"""
    from telegram_bot.results_tracker import load_picks
    
    args = context.args if context.args else []
    ad_type = args[0].lower() if args else 'promo'
    
    if ad_type == 'results':
        picks = load_picks()
        wins = sum(1 for p in picks if p['result'] == 'won')
        losses = sum(1 for p in picks if p['result'] == 'lost')
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        
        msg = f"📊 TODAY'S RESULTS\n"
        msg += f"━━━━━━━━━━━━━━━━━\n\n"
        msg += f"✅ {wins}W - ❌ {losses}L\n"
        msg += f"📈 Win Rate: {wr:.0f}%\n\n"
        if wr >= 80:
            msg += f"🔥 ANOTHER DOMINANT DAY 🔥\n\n"
        elif wr >= 60:
            msg += f"💪 Consistent profits 💪\n\n"
        msg += f"All picks are signal-stacked:\n"
        msg += f"✅ 5-signal quality filter\n"
        msg += f"✅ Trending form + xG regression\n"
        msg += f"✅ Draw trap elimination\n"
        msg += f"✅ Max 3 quality picks/day\n\n"
        msg += f"📩 Join: @FlightToProfit\n"
        msg += f"🤖 Powered by AI + data science"
    
    elif ad_type == 'challenge':
        msg = f"🏆 THE $10 → $10,000 CHALLENGE\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"Can our AI predictor turn\n"
        msg += f"$10 into $10,000 in 12 days?\n\n"
        msg += f"📊 How it works:\n"
        msg += f"• AI analyzes 26 leagues daily\n"
        msg += f"• 5-signal filter on every pick\n"
        msg += f"• Max 3 picks/day (quality > quantity)\n"
        msg += f"• Full transparency — every bet tracked\n\n"
        msg += f"🎯 Follow the challenge LIVE\n"
        msg += f"📩 Join: @FlightToProfit\n"
        msg += f"💰 VIP Access: $20/month"
    
    elif ad_type == 'vip':
        msg = f"🔒 VIP ACCESS — FlightToProfit\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"What you get:\n\n"
        msg += f"🤖 AI-Powered Predictions\n"
        msg += f"   Pure data science, not gut feelings\n\n"
        msg += f"📊 5-Signal Stack on EVERY Pick\n"
        msg += f"   Home form | Away veto | Bounce detect\n"
        msg += f"   GK check | Model confidence\n\n"
        msg += f"⭐ Star Rating System (1-5)\n"
        msg += f"📈 Trending Form + xG Regression\n"
        msg += f"🌤️ Weather + Pitcher Analysis\n"
        msg += f"🏆 Live Bankroll Challenges\n\n"
        msg += f"💰 Price: $20/month\n"
        msg += f"📩 DM to join VIP\n"
        msg += f"FlightToProfit ✈️"
    
    else:  # promo
        msg = f"✈️ FlightToProfit\n"
        msg += f"━━━━━━━━━━━━━━━━━\n\n"
        msg += f"🤖 AI Sports Predictor\n"
        msg += f"26 leagues | 5-signal filter | Data > gut\n\n"
        msg += f"📊 What makes us different:\n"
        msg += f"• We DON'T guess — AI crunches data\n"
        msg += f"• We DON'T spam 15 picks — max 3\n"
        msg += f"• We DON'T hide losses — full transparency\n"
        msg += f"• We DON'T sell fixed matches\n\n"
        msg += f"🔬 Our Edge:\n"
        msg += f"• Trending form vs static analysis\n"
        msg += f"• xG regression detection\n"
        msg += f"• Draw trap elimination\n"
        msg += f"• Weather impact modeling\n\n"
        msg += f"📩 Free: @FlightToProfit\n"
        msg += f"🔒 VIP ($20/mo): DM for access"
    
    await update.message.reply_text(msg)
