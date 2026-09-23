TELEGRAM_BOT_TOKEN = '8689367924:AAEVniggbG8SRfSPMLcfF8UQQfV0ws-XOfg'
ODDS_API_KEY = ''
TELEGRAM_CHAT_ID = ''
TIMEZONE = 'Asia/Beirut'
DAILY_PICKS_HOUR = 6
DAILY_PICKS_MINUTE = 0
MIN_CONFIDENCE = 0.70
MIN_VALUE_EDGE = 0.10
CONFIDENCE_TIERS = {'FIRE': 0.80, 'SOLID': 0.70, 'LEAN': 0.60}
ESPN_BASE_URL = 'https://site.web.api.espn.com/apis/site/v2/sports'
MLB_API_BASE = 'https://statsapi.mlb.com/api/v1'
ODDS_API_BASE = 'https://api.the-odds-api.com/v4'
SUPPORTED_SPORTS = {
    # --- BASEBALL ---
    'MLB': 'baseball/mlb',
    # --- BASKETBALL ---
    'NBA': 'basketball/nba',
    # --- TOP 5 SOCCER LEAGUES ---
    'EPL': 'soccer/eng.1',
    'La Liga': 'soccer/esp.1',
    'Bundesliga': 'soccer/ger.1',
    'Serie A': 'soccer/ita.1',
    'Ligue 1': 'soccer/fra.1',
    # --- SECOND TIER EUROPE ---
    'Eredivisie': 'soccer/ned.1',
    'Primeira Liga': 'soccer/por.1',
    'Belgian Pro': 'soccer/bel.1',
    'Scottish Prem': 'soccer/sco.1',
    'Super Lig': 'soccer/tur.1',
    'Greek Super League': 'soccer/gre.1',
    'Swiss Super League': 'soccer/sui.1',
    'Austrian Bundesliga': 'soccer/aut.1',
    # --- UEFA CLUB ---
    'Champions League': 'soccer/uefa.champions',
    'Europa League': 'soccer/uefa.europa',
    'Conference League': 'soccer/uefa.europa.conf',
    # --- AMERICAS ---
    'MLS': 'soccer/usa.1',
    'Liga MX': 'soccer/mex.1',
    'Brasileirao': 'soccer/bra.1',
    'Argentine Liga': 'soccer/arg.1',
    # --- OTHER ---
    'Saudi Pro League': 'soccer/ksa.1',
    'J-League': 'soccer/jpn.1',
    'A-League': 'soccer/aus.1',
    # --- ENGLISH LOWER ---
    'Championship': 'soccer/eng.2',
}
ODDS_API_SPORT_KEYS = {
    'MLB': 'baseball_mlb',
    'NBA': 'basketball_nba',
    'EPL': 'soccer_epl',
    'La Liga': 'soccer_spain_la_liga',
    'Bundesliga': 'soccer_germany_bundesliga',
    'Serie A': 'soccer_italy_serie_a',
    'Ligue 1': 'soccer_france_ligue_one',
    'MLS': 'soccer_usa_mls',
    'Champions League': 'soccer_uefa_champs_league',
    'Europa League': 'soccer_uefa_europa_league',
    'Super Lig': 'soccer_turkey_super_league',
    'Eredivisie': 'soccer_netherlands_eredivisie',
    'Primeira Liga': 'soccer_portugal_primeira_liga',
    'Liga MX': 'soccer_mexico_ligamx',
    'Brasileirao': 'soccer_brazil_campeonato',
    'Argentine Liga': 'soccer_argentina_primera_division',
    'Championship': 'soccer_england_efl_cup',
}
DB_PATH = 'db/golazo.db'
HOME_ADVANTAGE_ELO = 65
ELO_K_FACTOR = 32
ELO_INITIAL = 1500
FORM_GAMES = 10
H2H_GAMES = 5
