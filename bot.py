"""
FlightToProfit v7 — RENDER WEBHOOK EDITION.
Webhook-based. Render wakes it on every message. Free forever.
"""
import logging
import os
import sys

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('FlightToProfit')

def main():
    import config
    from telegram.ext import ApplicationBuilder
    from telegram_bot.handlers import setup_handlers
    from telegram_bot.scheduler import setup_scheduler

    if not getattr(config, 'TELEGRAM_BOT_TOKEN', None):
        logger.error('No TELEGRAM_BOT_TOKEN!')
        sys.exit(1)

    PORT = int(os.environ.get('PORT', 10000))
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://flighttoprofit.onrender.com')
    WEBHOOK_PATH = f'/webhook'
    WEBHOOK_URL = f'{RENDER_URL}{WEBHOOK_PATH}'

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

    logger.info('✈️ FlightToProfit v7 — RENDER WEBHOOK EDITION')
    logger.info(f'🌐 Webhook: {WEBHOOK_URL}')
    logger.info(f'🏟️ Leagues: {len(config.SUPPORTED_SPORTS)}')

    if not getattr(config, 'ODDS_API_KEY', None):
        logger.warning('⚠️ No Odds API key. Value detection limited.')

    # run_webhook handles everything: sets webhook with Telegram, starts web server
    app.run_webhook(
        listen='0.0.0.0',
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
