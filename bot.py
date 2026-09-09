import logging
import sys
from telegram.ext import ApplicationBuilder
import config
from telegram_bot.handlers import setup_handlers
from telegram_bot.scheduler import setup_scheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('FlightToProfit')

def main():
    # Check for bot token
    if not getattr(config, 'TELEGRAM_BOT_TOKEN', None):
        print('\n❌ ERROR: No Telegram Bot Token configured!')
        print('1. Open @BotFather on Telegram')
        print('2. Send /newbot and follow instructions')
        print('3. Copy the token and paste it in config.py')
        print('   TELEGRAM_BOT_TOKEN = "your-token-here"\n')
        sys.exit(1)
    
    # Build application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Setup handlers and get instances
    instances = setup_handlers(app)
    
    # Setup daily scheduler
    setup_scheduler(app, **instances)
    
    # Start bot
    logger.info('✈️ FlightToProfit is LIVE!')
    hour = getattr(config, 'DAILY_PICKS_HOUR', 21)
    minute = getattr(config, 'DAILY_PICKS_MINUTE', 0)
    tz = getattr(config, 'TIMEZONE', 'Asia/Beirut')
    logger.info(f'📅 Daily picks scheduled for {hour}:{minute:02d} {tz}')
    
    if not getattr(config, 'ODDS_API_KEY', None):
        logger.warning('⚠️ No Odds API key configured. Value detection will be limited.')
        logger.warning('   Get a free key at: https://the-odds-api.com')
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
