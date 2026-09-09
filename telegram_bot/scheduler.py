import logging
from datetime import time, datetime
import pytz
from telegram.ext import Application
import config

logger = logging.getLogger(__name__)

async def send_daily_picks(context):
    """Job to send daily picks automatically."""
    job_data = context.job.data
    db = job_data.get('db')
    espn = job_data.get('espn')
    mlb = job_data.get('mlb')
    predictor = job_data.get('predictor')
    
    chat_id = getattr(config, 'TELEGRAM_CHAT_ID', None)
    if not chat_id and db:
        chat_id = db.get_setting('chat_id')
        
    if not chat_id:
        logger.warning("No chat_id configured. Skipping daily picks.")
        return
        
    try:
        from telegram_bot import formatters
        
        # ESPN covers all sports including MLB
        matches = espn.get_todays_matches() if espn else []
        
        # Enrich with real team data
        enricher = job_data.get('enricher')
        if enricher and matches:
            matches = enricher.enrich_matches(matches)
        
        predictions = predictor.get_best_bets(matches) if predictor else []
        
        msg = formatters.format_daily_picks(predictions)
        
        # Telegram max message length is 4096
        if len(msg) > 4000:
            chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
            for chunk in chunks:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
        else:
            await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        logger.error(f"Error sending daily picks: {e}")

def setup_scheduler(application: Application, **kwargs):
    """Sets up the daily scheduler for automatic picks."""
    job_queue = application.job_queue
    if not job_queue:
        logger.warning("No JobQueue available. Scheduler not setup.")
        return
        
    tz_str = getattr(config, 'TIMEZONE', 'Asia/Beirut')
    try:
        tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC
        
    target_time = time(
        hour=getattr(config, 'DAILY_PICKS_HOUR', 21),
        minute=getattr(config, 'DAILY_PICKS_MINUTE', 0),
        tzinfo=tz
    )
    
    job_queue.run_daily(
        send_daily_picks,
        time=target_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        data=kwargs
    )
    
    logger.info(f"Scheduler setup for {target_time.strftime('%H:%M %Z')} daily.")
