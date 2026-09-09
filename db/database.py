import sqlite3
import os
import logging
from typing import Dict, List
import config
from data.models import BetRecord

logger = logging.getLogger(__name__)

class Database:
    """SQLite Database Manager for GOLAZO."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or getattr(config, 'DB_PATH', 'db/golazo.db')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

    def _create_tables(self):
        """Creates necessary tables if they do not exist."""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS elo_ratings (
                team_id TEXT PRIMARY KEY,
                sport TEXT,
                league TEXT,
                rating REAL,
                updated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                match_description TEXT,
                bet_type TEXT,
                odds REAL,
                stake REAL,
                result TEXT,
                profit REAL,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bankroll (
                id INTEGER PRIMARY KEY,
                balance REAL,
                updated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        self.conn.commit()

    def save_elo_rating(self, team_id: str, sport: str, league: str, rating: float):
        """Saves or updates an Elo rating."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO elo_ratings (team_id, sport, league, rating, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (team_id, sport, league, rating))
        self.conn.commit()

    def load_elo_ratings(self) -> Dict[str, float]:
        """Loads all Elo ratings."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT team_id, rating FROM elo_ratings')
        return {row[0]: row[1] for row in cursor.fetchall()}

    def save_bet(self, bet: BetRecord):
        """Saves a new bet record to history."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO bet_history (date, match_description, bet_type, odds, stake, result, profit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (bet.date, bet.match_description, bet.bet_type, bet.odds, bet.stake, bet.result, bet.profit))
        self.conn.commit()

    def get_bet_history(self, limit: int = 20) -> List[BetRecord]:
        """Gets recent betting history."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, date, match_description, bet_type, odds, stake, result, profit FROM bet_history ORDER BY id DESC LIMIT ?', (limit,))
        bets = []
        for row in cursor.fetchall():
            bets.append(BetRecord(
                id=row[0], date=row[1], match_description=row[2], bet_type=row[3], 
                odds=row[4], stake=row[5], result=row[6], profit=row[7]
            ))
        return bets

    def get_bankroll(self) -> float:
        """Gets the current bankroll balance."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM bankroll WHERE id = 1')
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def update_bankroll(self, amount: float):
        """Updates the bankroll balance."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO bankroll (id, balance, updated_at)
            VALUES (1, ?, datetime('now'))
        ''', (amount,))
        self.conn.commit()

    def get_stats(self) -> dict:
        """Calculates and returns betting stats."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT count(*), sum(case when result="win" then 1 else 0 end), sum(case when result="loss" then 1 else 0 end), sum(profit) FROM bet_history')
        row = cursor.fetchone()
        
        total_bets = row[0] or 0
        wins = row[1] or 0
        losses = row[2] or 0
        total_profit = row[3] or 0.0
        
        win_rate = (wins / total_bets) * 100 if total_bets > 0 else 0.0
        
        cursor.execute('SELECT sum(stake) FROM bet_history')
        stake_row = cursor.fetchone()
        total_stake = stake_row[0] or 0.0
        roi = (total_profit / total_stake) * 100 if total_stake > 0 else 0.0

        return {
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'roi': roi
        }

    def save_setting(self, key: str, value: str):
        """Saves a generic setting key/value pair."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()

    def get_setting(self, key: str, default: str = '') -> str:
        """Gets a setting value by key."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def close(self):
        """Closes the DB connection."""
        self.conn.close()
