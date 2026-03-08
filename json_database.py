import json
import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class JSONDatabase:
    """JSON база данных для бота"""
    
    def __init__(self, db_path: str = "bot_data.json"):
        self.db_path = db_path
        self.data = {
            "users": {},
            "settings": {
                "trade": True,
                "mines": True,
                "slots": True,
                "wheel": True
            },
            "last_save": None
        }
        self._lock = asyncio.Lock()
    
    async def load_data(self):
        """Загрузить данные из файла"""
        def _load():
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.data
        
        try:
            loaded_data = await asyncio.get_event_loop().run_in_executor(None, _load)
            self.data.update(loaded_data)
        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")
            self.data = {"users": {}, "settings": {"trade": True, "mines": True, "slots": True, "wheel": True}}
    
    async def save_data(self):
        """Сохранить данные в файл"""
        def _save():
            self.data["last_save"] = datetime.now().isoformat()
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        
        try:
            await asyncio.get_event_loop().run_in_executor(None, _save)
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя"""
        async with self._lock:
            return self.data["users"].get(str(user_id))
    
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Добавить пользователя"""
        async with self._lock:
            if str(user_id) not in self.data["users"]:
                self.data["users"][str(user_id)] = {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "balance": 1000,
                    "bank_balance": 0,
                    "registration_date": datetime.now().isoformat(),
                    "avatar_path": None,
                    "is_banned": False,
                    "profile_closed": False,
                    "daily_winnings": 0,
                    "last_bonus_date": None
                }
                await self.save_data()
    
    async def update_balance(self, user_id: int, amount: int):
        """Обновить баланс"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["balance"] += amount
                await self.save_data()
    
    async def update_bank_balance(self, user_id: int, amount: int):
        """Обновить баланс банка"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["bank_balance"] += amount
                await self.save_data()
    
    async def update_daily_winnings(self, user_id: int, amount: int):
        """Обновить ежедневные выигрыши"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["daily_winnings"] += amount
                await self.save_data()
    
    async def update_avatar(self, user_id: int, avatar_path: Optional[str]):
        """Обновить аватар"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["avatar_path"] = avatar_path
                await self.save_data()
    
    async def ban_user(self, user_id: int):
        """Забанить пользователя"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["is_banned"] = True
                await self.save_data()
    
    async def unban_user(self, user_id: int):
        """Разбанить пользователя"""
        async with self._lock:
            user_id_str = str(user_id)
            if user_id_str in self.data["users"]:
                self.data["users"][user_id_str]["is_banned"] = False
                await self.save_data()
    
    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Получить топ пользователей по балансу"""
        async with self._lock:
            users = [user for user in self.data["users"].values() if not user["is_banned"]]
            users.sort(key=lambda x: x["balance"], reverse=True)
            return users[:limit]
    
    async def get_top_banks(self, limit: int = 10) -> List[Dict]:
        """Получить топ пользователей по банку"""
        async with self._lock:
            users = [user for user in self.data["users"].values() 
                    if not user["is_banned"] and user["bank_balance"] > 0]
            users.sort(key=lambda x: x["bank_balance"], reverse=True)
            return users[:limit]
    
    async def get_leaderboard(self, limit: int = 5) -> List[Dict]:
        """Получить лидерборд по ежедневным выигрышам"""
        async with self._lock:
            users = [user for user in self.data["users"].values() 
                    if not user["is_banned"] and user["daily_winnings"] > 0]
            users.sort(key=lambda x: x["daily_winnings"], reverse=True)
            return users[:limit]
    
    async def get_game_settings(self) -> Dict[str, bool]:
        """Получить настройки игр"""
        async with self._lock:
            return self.data["settings"].copy()
    
    async def toggle_game(self, game_name: str, enabled: bool):
        """Переключить игру"""
        async with self._lock:
            if game_name in self.data["settings"]:
                self.data["settings"][game_name] = enabled
                await self.save_data()
    
    async def transfer_money(self, from_user_id: int, to_user_id: int, amount: int):
        """Перевод денег"""
        async with self._lock:
            from_user_str = str(from_user_id)
            to_user_str = str(to_user_id)
            
            if (from_user_str in self.data["users"] and 
                to_user_str in self.data["users"] and
                self.data["users"][from_user_str]["balance"] >= amount):
                
                self.data["users"][from_user_str]["balance"] -= amount
                self.data["users"][to_user_str]["balance"] += amount
                await self.save_data()
                return True
            return False
    
    async def reset_daily_winnings(self):
        """Сбросить ежедневные выигрыши"""
        async with self._lock:
            for user in self.data["users"].values():
                user["daily_winnings"] = 0
            await self.save_data()
    
    def get_file_size(self) -> int:
        """Получить размер файла"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0
    
    def get_last_save(self) -> Optional[str]:
        """Получить время последнего сохранения"""
        return self.data.get("last_save")
