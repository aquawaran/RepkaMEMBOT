import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import Bot, F

class RouletteGame:
    def __init__(self, database):
        self.db = database
        self.bets: Dict[int, Dict] = {}  # bets[chat_id] = {user_id: {amount: int, bet_type: str, bet_value: str}}
        self.rounds: Dict[int, Dict] = {}  # rounds[chat_id] = {active: bool, last_bet_time: float, last_go_time: float}
        self.history: Dict[int, List[int]] = {}  # history[chat_id] = [numbers]
        
        # Настройки рулетки
        self.numbers = list(range(1, 37))  # Числа от 1 до 36
        self.red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        self.black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        self.green_number = 0  # Зеро
        
        self.MIN_BET = 100
        self.BET_COOLDOWN = 10  # секунд после ставки перед запуском
        self.GO_COOLDOWN = 5  # секунд между запусками рулетки
        
    def get_number_color(self, number: int) -> str:
        """Определить цвет числа"""
        if number == self.green_number:
            return "зеленый"
        elif number in self.red_numbers:
            return "красный"
        else:
            return "черный"
    
    def calculate_multiplier(self, bet_type: str, bet_value: str) -> float:
        """Рассчитать множитель для ставки"""
        if bet_type == "число":
            return 35.0
        elif bet_type == "цвет":
            if bet_value.lower() in ["красный", "черный"]:
                return 2.0
            elif bet_value.lower() == "зеленый":
                return 35.0
        elif bet_type == "диапазон":
            # Разбираем диапазон типа "10-25"
            try:
                start, end = map(int, bet_value.split('-'))
                count = end - start + 1
                return 35.0 / count
            except:
                return 1.0
        elif bet_type in ["odd", "even"]:
            return 2.0
        return 1.0
    
    def check_win(self, number: int, bet_type: str, bet_value: str) -> bool:
        """Проверить выиграла ли ставка"""
        if bet_type == "число":
            return str(number) == bet_value
        elif bet_type == "цвет":
            color = self.get_number_color(number)
            return color.lower() == bet_value.lower()
        elif bet_type == "диапазон":
            try:
                start, end = map(int, bet_value.split('-'))
                return start <= number <= end
            except:
                return False
        elif bet_type == "odd":
            return number % 2 == 1
        elif bet_type == "even":
            return number % 2 == 0
        return False
    
    async def place_bet(self, message: Message, amount: int, bet_values: List[str]):
        """Сделать ставку (поддерживает множественные ставки)"""
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Проверяем минимальную ставку
        if amount < self.MIN_BET:
            await message.reply(f"❌ Минимальная ставка: {self.MIN_BET} MEM")
            return
        
        # Получаем пользователя
        user = await self.db.get_user(user_id)
        if not user:
            await message.reply("❌ Пользователь не найден")
            return
        
        # Проверяем баланс
        if user['balance'] < amount * len(bet_values):
            await message.reply(f"❌ Недостаточно средств. Нужно: {amount * len(bet_values)} MEM")
            return
        
        # Инициализируем чат если нужно
        if chat_id not in self.bets:
            self.bets[chat_id] = {}
        if chat_id not in self.rounds:
            self.rounds[chat_id] = {"active": False, "last_bet_time": 0, "last_go_time": 0}
        if chat_id not in self.history:
            self.history[chat_id] = []
        
        # Обрабатываем каждую ставку
        successful_bets = []
        total_bet_amount = 0
        
        for bet_value in bet_values:
            # Определяем тип и множитель ставки
            bet_type, multiplier = self.parse_bet_value(bet_value)
            
            if multiplier <= 0:
                await message.reply(f"❌ Неверный формат ставки: {bet_value}")
                continue
            
            # Добавляем ставку
            if user_id not in self.bets[chat_id]:
                self.bets[chat_id][user_id] = []
            
            self.bets[chat_id][user_id].append({
                "amount": amount,
                "bet_type": bet_type,
                "bet_value": bet_value,
                "multiplier": multiplier,
                "user_name": message.from_user.first_name
            })
            
            successful_bets.append(f"✅ {bet_value} ({multiplier:.1f}x)")
            total_bet_amount += amount
        
        if not successful_bets:
            await message.reply("❌ Ни одна ставка не была принята")
            return
        
        # Списываем средства
        await self.db.update_balance(user_id, -total_bet_amount)
        
        # Обновляем время последней ставки
        self.rounds[chat_id]["last_bet_time"] = time.time()
        
        # Формируем сообщение о ставке
        bet_text = f"💰 Ставки приняты: {len(successful_bets)} шт. по {amount} MEM каждая\n"
        bet_text += f"📋 Список ставок:\n" + "\n".join(successful_bets) + "\n"
        bet_text += f"💸 Всего списано: {total_bet_amount} MEM\n\n"
        
        # Показываем текущие ставки в чате
        total_bets = self.get_total_bets(chat_id)
        bet_text += f"📊 Общие ставки в раунде: {total_bets} MEM"
        bet_text += f"\n🎯 Для запуска рулетки напишите: ГО"
        
        await message.reply(bet_text)
    
    def parse_bet_value(self, bet_value: str) -> Tuple[str, float]:
        """Распарсить значение ставки и вернуть (тип, множитель)"""
        bet_value_lower = bet_value.lower()
        
        # Чет/нечет
        if bet_value_lower in ["odd", "even", "одд", "евен"]:
            bet_type = "odd" if bet_value_lower in ["odd", "одд"] else "even"
            return bet_type, 2.0
        
        # Цвета (включая сокращения)
        if bet_value_lower in ["красный", "черный", "к", "ч"]:
            if bet_value_lower in ["красный", "к"]:
                return "цвет", 2.0
            else:  # черный, ч
                return "цвет", 2.0
        elif bet_value_lower == "зеленый":
            return "цвет", 35.0
        
        # Диапазон - проверяем СНАЧАЛА что это диапазон
        if "-" in bet_value and not bet_value.replace("-", "").replace(" ", "").isdigit():
            try:
                # Разделяем по дефису, убираем пробелы только вокруг чисел
                parts = bet_value.split("-")
                if len(parts) == 2:
                    start_str = parts[0].strip()
                    end_str = parts[1].strip()
                    start = int(start_str)
                    end = int(end_str)
                    count = end - start + 1
                    if count > 0 and count <= 36 and start >= 0 and end <= 36:
                        return "диапазон", 35.0 / count
            except:
                pass
        
        # Число - проверяем что это именно число, а не часть диапазона
        if bet_value.isdigit() and len(bet_value) <= 2:  # числа от 0 до 36
            num = int(bet_value)
            if 0 <= num <= 36:
                return "число", 35.0
        
        return "", 0.0
    
    def get_total_bets(self, chat_id: int) -> int:
        """Получить общую сумму ставок в раунде"""
        if chat_id not in self.bets:
            return 0
        
        total = 0
        for user_bets in self.bets[chat_id].values():
            for bet in user_bets:
                total += bet["amount"]
        return total
    
    async def start_round(self, message: Message):
        """Запустить раунд рулетки"""
        chat_id = message.chat.id
        current_time = time.time()
        
        # Инициализируем чат если нужно
        if chat_id not in self.rounds:
            self.rounds[chat_id] = {"active": False, "last_bet_time": 0, "last_go_time": 0}
        
        # Проверяем кулдаун после последней ставки
        if current_time - self.rounds[chat_id]["last_bet_time"] < self.BET_COOLDOWN:
            remaining = int(self.BET_COOLDOWN - (current_time - self.rounds[chat_id]["last_bet_time"]))
            await message.reply(f"⏳ Запуск рулетки доступен через {remaining} секунд после последней ставки")
            return
        
        # Проверяем кулдаун между запусками
        if current_time - self.rounds[chat_id]["last_go_time"] < self.GO_COOLDOWN:
            remaining = int(self.GO_COOLDOWN - (current_time - self.rounds[chat_id]["last_go_time"]))
            await message.reply(f"⏳ Рулетка уже запущена! Следующий запуск через {remaining} секунд")
            return
        
        # Проверяем есть ли ставки
        if chat_id not in self.bets or not self.bets[chat_id]:
            await message.reply("❌ Нет ставок для запуска рулетки")
            return
        
        # Устанавливаем флаг активного раунда
        self.rounds[chat_id]["active"] = True
        self.rounds[chat_id]["last_go_time"] = current_time
        
        # Генерируем выпавшее число
        winning_number = random.choice(self.numbers)
        winning_color = self.get_number_color(winning_number)
        
        # Добавляем в историю
        self.history[chat_id].append(winning_number)
        if len(self.history[chat_id]) > 10:
            self.history[chat_id] = self.history[chat_id][-10:]
        
        # Отправляем анимацию запуска
        await message.reply("🎰 Рулетка запускается...")
        await asyncio.sleep(2)
        
        # Показываем результат
        result_text = f"🎯 Выпало число: {winning_number} ({winning_color})\n\n"
        
        total_winnings = 0
        winners = []
        
        # Обрабатываем все ставки
        for user_id, user_bets in self.bets[chat_id].items():
            user_winnings = 0
            user_results = []
            
            for bet in user_bets:
                if self.check_win(winning_number, bet["bet_type"], bet["bet_value"]):
                    win_amount = int(bet["amount"] * bet["multiplier"])
                    user_winnings += win_amount
                    user_results.append(f"✅ {bet['bet_type']} {bet['bet_value']}: +{win_amount} MEM")
                else:
                    user_results.append(f"❌ {bet['bet_type']} {bet['bet_value']}: -{bet['amount']} MEM")
            
            # Выплачиваем выигрыш
            if user_winnings > 0:
                await self.db.update_balance(user_id, user_winnings)
                total_winnings += user_winnings
                winners.append(f"💰 {bet['user_name']}: +{user_winnings} MEM")
            
            # Добавляем в историю игр
            for bet in user_bets:
                result = "win" if self.check_win(winning_number, bet["bet_type"], bet["bet_value"]) else "lose"
                win_amount = int(bet["amount"] * bet["multiplier"]) if result == "win" else 0
                await self.db.add_game_history(user_id, "Рулетка", bet["amount"], result, win_amount)
        
        # Показываем результаты
        if winners:
            result_text += "🏆 Победители:\n" + "\n".join(winners) + "\n\n"
        
        result_text += f"💰 Всего выплачено: {total_winnings} MEM"
        
        # Очищаем ставки
        self.bets[chat_id] = {}
        self.rounds[chat_id]["active"] = False
        
        await message.reply(result_text)
    
    async def show_history(self, message: Message):
        """Показать историю последних 10 чисел"""
        chat_id = message.chat.id
        
        if chat_id not in self.history or not self.history[chat_id]:
            await message.reply("📋 История пуста")
            return
        
        history_text = "📋 Последние 10 чисел:\n\n"
        
        for i, number in enumerate(self.history[chat_id], 1):
            color = self.get_number_color(number)
            color_emoji = {"красный": "🔴", "черный": "⚫", "зеленый": "🟢"}[color]
            history_text += f"{i}. {color_emoji} {number} ({color})\n"
        
        await message.reply(history_text)
    
    async def show_help(self, message: Message):
        """Показать помощь по игре"""
        help_text = "🎰 РУЛЕТКА - ПРАВИЛА ИГРЫ\n\n"
        help_text += f"💰 Минимальная ставка: {self.MIN_BET} MEM\n\n"
        help_text += "📋 КОМАНДЫ:\n"
        help_text += "• Рулетка/РУЛ [ставка] [ставки...] - сделать ставки\n"
        help_text += "• ГО - запустить рулетку\n"
        help_text += "• Лог - показать историю\n\n"
        help_text += "🎯 ТИПЫ СТАВОК:\n"
        help_text += "• Число: Рулетка 1000 7 (выплата 35x)\n"
        help_text += "• Цвет: Рулетка 1000 красный/к (2x), черный/ч (2x), зеленый (35x)\n"
        help_text += "• Диапазон: Рулетка 1000 10-20 (35x/кол-во чисел)\n"
        help_text += "• Чет/Нечет: Рулетка 1000 odd/even (2x)\n\n"
        help_text += "🎲 МНОЖЕСТВЕННЫЕ СТАВКИ:\n"
        help_text += "• РУЛ 1000 1 3 5 12-16 17-19 27\n"
        help_text += "• РУЛ 500 к ч odd 1-18\n\n"
        help_text += "⏱️ После ставки нужно подождать 10 секунд перед запуском\n"
        help_text += "🎮 Игра доступна только в чатах!"
        
        await message.reply(help_text)

# Глобальный экземпляр игры
roulette_game = None

def init_roulette(database):
    global roulette_game
    roulette_game = RouletteGame(database)
    return roulette_game
