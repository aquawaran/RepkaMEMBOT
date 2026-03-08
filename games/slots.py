import random
from typing import Dict, Optional
from aiogram.types import Message

class SlotsGame:
    """Игра Слоты - вращение барабанов с эмодзи"""
    
    def __init__(self, database):
        self.db = database
        
        # Эмодзи для слотов
        self.symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "⭐", "💎", "7️⃣"]
        
        # Таблица выплат
        self.payouts = {
            "7️⃣7️⃣7️⃣": 50,  # Три семерки
            "💎💎💎": 30,   # Три бриллианта
            "⭐⭐⭐": 20,    # Три звезды
            "🍉🍉🍉": 15,    # Три арбуза
            "🍇🍇🍇": 12,    # Три винограда
            "🍊🍊🍊": 10,    # Три апельсина
            "🍋🍋🍋": 8,     # Три лимона
            "🍒🍒🍒": 5,     # Три вишни
        }
        
        # Выплаты для пар
        self.pair_payouts = {
            "7️⃣7️⃣": 5,
            "💎💎": 3,
            "⭐⭐": 2,
            "🍉🍉": 1.5,
            "🍇🍇": 1.2,
            "🍊🍊": 1,
            "🍋🍋": 0.8,
            "🍒🍒": 0.5,
        }
    
    async def play(self, message: Message, bet: int) -> bool:
        """Играть в слоты"""
        user_id = message.from_user.id
        user = await self.db.get_user(user_id)
        
        if not user or user['balance'] < bet:
            await message.reply("❌ Недостаточно MEM для ставки")
            return False
        
        if bet < 100:
            await message.reply("❌ Минимальная ставка: 100 MEM")
            return False
        
        if bet <= 0:
            await message.reply("❌ Ставка должна быть больше 0")
            return False
        
        # Списываем ставку
        await self.db.update_balance(user_id, -bet)
        
        # Генерируем результат
        result = self._spin_slots()
        
        # Рассчитываем выигрыш
        win_amount = self._calculate_win(result, bet)
        
        if win_amount > 0:
            await self.db.update_balance(user_id, win_amount)
            await self.db.update_daily_winnings(user_id, win_amount - bet)
        
        # Отправляем результат
        await self._send_result(message, result, bet, win_amount)
        return True
    
    def _spin_slots(self) -> list:
        """Вращение слотов"""
        return [random.choice(self.symbols) for _ in range(3)]
    
    def _calculate_win(self, result: list, bet: int) -> int:
        """Рассчитать выигрыш"""
        result_str = "".join(result)
        
        # Проверяем три одинаковых
        if result_str in self.payouts:
            return int(bet * self.payouts[result_str])
        
        # Проверяем пару
        for symbol in self.symbols:
            if result.count(symbol) == 2:
                pair_key = f"{symbol}{symbol}"
                if pair_key in self.pair_payouts:
                    return int(bet * self.pair_payouts[pair_key])
        
        return 0
    
    async def _send_result(self, message: Message, result: list, bet: int, win_amount: int):
        """Отправить результат игры с анимацией"""
        import asyncio
        
        # Отправляем первоначальное сообщение с закрытыми ячейками
        initial_text = "🎰 СЛОТЫ 🎰\n\n"
        initial_text += f"📊 Ставка: {bet} MEM\n\n"
        initial_text += "❓ ❓ ❓"
        
        sent_message = await message.reply(initial_text)
        
        # Постепенно открываем ячейки
        revealed_result = []
        for i, symbol in enumerate(result):
            await asyncio.sleep(0.5)  # Задержка 0.5 секунды
            revealed_result.append(symbol)
            
            # Обновляем сообщение
            current_text = "🎰 СЛОТЫ 🎰\n\n"
            current_text += f"📊 Ставка: {bet} MEM\n\n"
            current_text += " ".join(revealed_result + ["❓"] * (len(result) - len(revealed_result)))
            
            try:
                await sent_message.edit_text(current_text)
            except:
                pass  # Если не удалось отредактировать, продолжаем
        
        # Финальный результат
        await asyncio.sleep(0.5)
        
        final_text = "🎰 СЛОТЫ 🎰\n\n"
        final_text += f"📊 Ставка: {bet} MEM\n\n"
        final_text += f"{' '.join(result)}\n\n"
        
        if win_amount > 0:
            final_text += f"🎉 Выигрыш: {win_amount} MEM!\n"
            final_text += f"💰 Прибыль: {win_amount - bet} MEM\n\n"
            
            # Определяем результат и множитель
            reels = result
            if reels[0] == reels[1] == reels[2]:
                # Три одинаковых символа
                if reels[0] == "💎":
                    multiplier = 5.0
                    result = "� ДЖЕКПОТ! ТРИ АЛМАЗА!"
                elif reels[0] == "7️⃣":
                    multiplier = 3.0
                    result = "🍀 СУПЕР УДАЧА! ТРИ СЕМЁРКИ!"
                elif reels[0] == "🍒":
                    multiplier = 2.0
                    result = "🎰 ОТЛИЧНО! ТРИ ВИШНИ!"
                else:
                    multiplier = 1.5
                    result = "✅ ХОРОШО! ТРИ ОДИНАКОВЫХ!"
            elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
                # Два одинаковых символа
                if "💎" in reels:
                    multiplier = 1.2
                    result = "💎 НЕПЛОХО! ДВА АЛМАЗА!"
                else:
                    multiplier = 1.1
                    result = "👍 НОРМАЛЬНО! ДВА ОДИНАКОВЫХ!"
            else:
                # Все разные
                multiplier = 0.0
                result = "😞 Попробуй еще раз!"
            
            final_text += f"{result}\n"
        else:
            final_text += f"😔 Проигрыш: {bet} MEM\n"
            final_text += "💸 Попробуйте еще раз!"
        
        try:
            await sent_message.edit_text(final_text)
        except:
            await message.reply(final_text)
    
    def get_rules(self) -> str:
        """Получить правила игры"""
        rules = "🎰 СЛОТЫ\n\n"
        rules += "📜 Правила:\n"
        rules += "• Минимальная ставка: 100 MEM\n"
        rules += "• Нужно выпадание 2 или 3 одинаковых эмодзи\n\n"
        rules += "💰 Выплаты:\n"
        rules += "• 7️⃣7️⃣7️⃣ - x50\n"
        rules += "• 💎💎💎 - x30\n"
        rules += "• ⭐⭐⭐ - x20\n"
        rules += "• 🍉🍉🍉 - x15\n"
        rules += "• 🍇🍇🍇 - x12\n"
        rules += "• 🍊🍊🍊 - x10\n"
        rules += "• 🍋🍋🍋 - x8\n"
        rules += "• 🍒🍒🍒 - x5\n\n"
        rules += "✨ Пары:\n"
        rules += "• 7️⃣7️⃣ - x5\n"
        rules += "• 💎💎 - x3\n"
        rules += "• ⭐⭐ - x2\n"
        rules += "• 🍉🍉 - x1.5\n"
        rules += "• 🍇🍇 - x1.2\n"
        rules += "• 🍊🍊 - x1\n"
        rules += "• 🍋🍋 - x0.8\n"
        rules += "• 🍒🍒 - x0.5\n\n"
        rules += "🎮 Команда: Слоты [ставка]"
        
        return rules
