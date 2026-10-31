"""
FlightToProfit v6 — UNSTOPPABLE EDITION.
Auto-restart on crash. Retry on disconnect. Never dies.
"""
import logging
import sys
import time
import signal
import traceback
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('FlightToProfit')

MAX_RETRIES = 999999  # Basically infinite
RETRY_DELAY_BASE = 5  # Start with 5 seconds
RETRY_DELAY_MAX = 300  # Cap at 5 minutes
CLEAN_RUN_THRESHOLD = 60  # If bot runs 60+ seconds, reset retry counter


def run_bot():
    """Single bot run attempt. Returns True if it ran cleanly, False on crash."""
    import config
    from telegram.ext import ApplicationBuilder
    from telegram_bot.handlers import setup_handlers
    from telegram_bot.scheduler import setup_scheduler

    if not getattr(config, 'TELEGRAM_BOT_TOKEN', None):
        logger.error('No TELEGRAM_BOT_TOKEN configured!')
        sys.exit(1)

    # Build with connection pool settings for resilience
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .connection_pool_size(8)
        .build()
    )

    instances = setup_handlers(app)
    setup_scheduler(app, **instances)

    logger.info('✈️ FlightToProfit v6 — UNSTOPPABLE EDITION')
    hour = getattr(config, 'DAILY_PICKS_HOUR', 6)
    minute = getattr(config, 'DAILY_PICKS_MINUTE', 0)
    tz = getattr(config, 'TIMEZONE', 'Asia/Beirut')
    logger.info(f'📅 Daily picks: {hour}:{minute:02d} {tz}')
    logger.info(f'🏟️ Leagues: {len(config.SUPPORTED_SPORTS)}')

    if not getattr(config, 'ODDS_API_KEY', None):
        logger.warning('⚠️ No Odds API key. Value detection limited.')

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=['message', 'callback_query'],
        close_loop=False
    )


def main():
    """
    IMMORTAL LOOP — the bot restarts itself on ANY crash.
    Exponential backoff on repeated failures, resets after clean runs.
    """
    retries = 0
    
    logger.info('=' * 50)
    logger.info('  FlightToProfit — IMMORTAL MODE')
    logger.info('  This bot does NOT stay dead.')
    logger.info('=' * 50)

    # Start health check server (Railway needs this)
    try:
        from healthcheck import start_health_server
        start_health_server()
    except Exception as e:
        logger.warning(f'Health server skipped: {e}')

    while retries < MAX_RETRIES:
        start_time = time.time()
        
        try:
            run_bot()
            # If run_bot returns cleanly (e.g., graceful shutdown), exit
            logger.info('Bot stopped gracefully.')
            break
            
        except KeyboardInterrupt:
            logger.info('Shutdown requested. Goodbye.')
            break
            
        except SystemExit as e:
            if e.code == 0:
                logger.info('Clean exit.')
                break
            logger.error(f'SystemExit with code {e.code}')
            
        except Exception as e:
            run_duration = time.time() - start_time
            
            # If it ran for a while before crashing, reset retry counter
            if run_duration > CLEAN_RUN_THRESHOLD:
                retries = 0
                logger.info(f'Ran for {run_duration:.0f}s before crash — resetting retry counter')
            
            retries += 1
            delay = min(RETRY_DELAY_BASE * (2 ** min(retries - 1, 6)), RETRY_DELAY_MAX)
            
            logger.error(f'💀 CRASH #{retries}: {type(e).__name__}: {e}')
            logger.error(traceback.format_exc())
            logger.info(f'🔄 Restarting in {delay}s...')
            
            time.sleep(delay)
            logger.info(f'🚀 Attempt #{retries + 1} — rising from the ashes...')
    
    if retries >= MAX_RETRIES:
        logger.error(f'Exhausted {MAX_RETRIES} retries. Something is deeply wrong.')
        sys.exit(1)


if __name__ == '__main__':
    main()
