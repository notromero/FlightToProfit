# 🎯 GOLAZO Predictor Bot

Sports betting prediction engine with Telegram bot delivery.

## Quick Setup (5 minutes)

### 1. Install Python dependencies
```bash
cd C:\Users\PC FACTORY\.gemini\antigravity\scratch\golazo-predictor
pip install -r requirements.txt
```

### 2. Create your Telegram Bot
1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts (give it a name like 'GOLAZO Predictor')
4. Copy the bot token

### 3. Configure
Open `config.py` and fill in:
- `TELEGRAM_BOT_TOKEN` = your bot token from step 2
- `ODDS_API_KEY` = get free key from https://the-odds-api.com (optional but recommended)
- `TELEGRAM_CHAT_ID` = your personal chat ID (the bot will auto-detect this when you /start)

### 4. Run
```bash
python bot.py
```

### 5. Start using
Open your bot in Telegram and send `/start`

## Commands
| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/picks` | Get today's high-confidence picks |
| `/tomorrow` | Get tomorrow's picks |
| `/analyze TeamName` | Deep analysis of a team |
| `/form TeamName` | Last 10 results |
| `/upcoming` | All upcoming matches |
| `/bankroll` | View bankroll stats |
| `/addbet stake odds win/loss` | Log a bet result |
| `/setbankroll amount` | Set initial bankroll |
| `/help` | Show all commands |

## How It Works
- Elo rating system tracks team strength
- Poisson model predicts expected scores
- Form analyzer weights recent performance
- H2H analyzer checks historical matchups
- Value detector compares model vs bookmaker odds
- Only recommends bets with 70%+ model confidence

## Sports Covered
MLB, NBA, Premier League, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Champions League, Europa League, Turkish Super Lig
