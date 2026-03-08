import sqlite3
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных"""
        def _init_db():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 1000,
                    bank_balance INTEGER DEFAULT 0,
                    registration_date TEXT,
                    avatar_path TEXT,
                    is_banned BOOLEAN DEFAULT FALSE,
                    profile_closed BOOLEAN DEFAULT FALSE,
                    daily_winnings INTEGER DEFAULT 0,
                    last_bonus_date TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    amount INTEGER,
                    transaction_type TEXT,
                    timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_settings (
                    game_name TEXT PRIMARY KEY,
                    is_enabled BOOLEAN DEFAULT TRUE
                )
            """)
            
            conn.commit()
            conn.close()
        
        # Выполняем в отдельном потоке
        await asyncio.get_event_loop().run_in_executor(None, _init_db)
    
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Добавление нового пользователя"""
        def _add_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, registration_date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _add_user)
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        def _get_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                columns = ['user_id', 'username', 'first_name', 'last_name', 'balance', 
                          'bank_balance', 'registration_date', 'avatar_path', 'is_banned',
                          'profile_closed', 'daily_winnings', 'last_bonus_date']
                return dict(zip(columns, row))
            return None
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_user)
    
    async def update_balance(self, user_id: int, amount: int) -> bool:
        """Обновление баланса пользователя"""
        def _update_balance():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _update_balance)
    
    async def update_bank_balance(self, user_id: int, amount: int) -> bool:
        """Обновление банковского баланса"""
        def _update_bank_balance():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET bank_balance = bank_balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _update_bank_balance)
    
    async def transfer_money(self, from_user_id: int, to_user_id: int, amount: int) -> bool:
        """Перевод денег между пользователями"""
        def _transfer_money():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Проверяем баланс отправителя
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (from_user_id,))
            sender_balance = cursor.fetchone()
            
            if not sender_balance or sender_balance[0] < amount:
                conn.close()
                return False
            
            # Выполняем перевод
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, from_user_id))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, to_user_id))
            
            # Записываем транзакцию
            cursor.execute("""
                INSERT INTO transactions (from_user_id, to_user_id, amount, transaction_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (from_user_id, to_user_id, amount, "transfer", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            conn.commit()
            conn.close()
            return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _transfer_money)
    
    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Получение топ пользователей по балансу"""
        def _get_top_users():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, balance 
                FROM users 
                WHERE is_banned = FALSE 
                ORDER BY balance DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            columns = ['user_id', 'username', 'first_name', 'balance', 
                      'bank_balance', 'registration_date', 'avatar_path', 'is_banned',
                      'profile_closed', 'daily_winnings', 'last_bonus_date']
            return [dict(zip(columns, row)) for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_top_users)
    
    async def get_top_banks(self, limit: int = 10) -> List[Dict]:
        """Получение топ банков"""
        def _get_top_banks():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, bank_balance 
                FROM users 
                WHERE is_banned = FALSE AND bank_balance > 0
                ORDER BY bank_balance DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            columns = ['user_id', 'username', 'first_name', 'last_name', 'balance', 
                      'bank_balance', 'registration_date', 'avatar_path', 'is_banned',
                      'profile_closed', 'daily_winnings', 'last_bonus_date']
            return [dict(zip(columns, row)) for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_top_banks)
    
    async def ban_user(self, user_id: int) -> bool:
        """Бан пользователя"""
        def _ban_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _ban_user)
    
    async def unban_user(self, user_id: int) -> bool:
        """Разбан пользователя"""
        def _unban_user():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = FALSE WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _unban_user)
    
    async def update_avatar(self, user_id: int, avatar_path: Optional[str]):
        """Обновление аватарки"""
        def _update_avatar():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET avatar_path = ? WHERE user_id = ?", (avatar_path, user_id))
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _update_avatar)
    
    async def toggle_profile(self, user_id: int, closed: bool) -> bool:
        """Закрыть/открыть профиль"""
        def _toggle_profile():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET profile_closed = ? WHERE user_id = ?", (closed, user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _toggle_profile)
    
    async def update_daily_winnings(self, user_id: int, amount: int) -> bool:
        """Обновление дневных выигрышей"""
        def _update_daily_winnings():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET daily_winnings = daily_winnings + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _update_daily_winnings)
    
    async def reset_daily_winnings(self):
        """Сброс дневных выигрышей (выполняется в 00:00)"""
        def _reset_daily_winnings():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET daily_winnings = 0")
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _reset_daily_winnings)
    
    async def get_leaderboard(self, limit: int = 5) -> List[Dict]:
        """Получение лидерборда"""
        def _get_leaderboard():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_banned = FALSE AND daily_winnings > 0 ORDER BY daily_winnings DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            columns = ['user_id', 'username', 'first_name', 'last_name', 'balance', 
                      'bank_balance', 'registration_date', 'avatar_path', 'is_banned',
                      'profile_closed', 'daily_winnings', 'last_bonus_date']
            return [dict(zip(columns, row)) for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_leaderboard)
    
    async def get_game_settings(self) -> Dict[str, bool]:
        """Получение настроек игр"""
        def _get_game_settings():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT game_name, is_enabled FROM game_settings")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return {}
            
            return {row[0]: bool(row[1]) for row in rows}
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_game_settings)
    
    async def toggle_game(self, game_name: str, enabled: bool) -> bool:
        """Включить/отключить игру"""
        def _toggle_game():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO game_settings (game_name, is_enabled)
                VALUES (?, ?)
            """, (game_name, enabled))
            conn.commit()
            conn.close()
            return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _toggle_game)
