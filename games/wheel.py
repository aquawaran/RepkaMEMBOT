import asyncio
import random
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

class WheelGame:
    def __init__(self, db: 'Database'):
        self.db = db
        self.active_games = {}  # user_id -> game_data
        self.wheel_cooldowns = {}  # user_id -> last_game_time
    
    async def start_game(self, message: Message):
        """Начать игру Вилин"""
        user_id = message.from_user.id
        current_time = time.time()
        
        # Проверяем кулдаун (1 минута)
        if user_id in self.wheel_cooldowns:
            time_diff = current_time - self.wheel_cooldowns[user_id]
            if time_diff < 60:  # 60 секунд
                remaining = int(60 - time_diff)
                await message.reply(f"⏳ Играть в Вилин можно раз в минуту. Подождите {remaining} секунд", reply_to_message_id=message.message_id)
                return
        
        # Получаем баланс пользователя
        user = await self.db.get_user(user_id)
        if not user:
            await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
            return
        
        balance = user['balance']
        
        # Проверяем минимальный баланс
        if balance < 100:
            await message.reply("❌ Минимальный баланс для игры: 100 MEM", reply_to_message_id=message.message_id)
            return
        
        # Создаем клавиатуру для выбора
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🎰 ВИЛИН!", callback_data="wheel_spin"))
        keyboard.add(InlineKeyboardButton(text="❌ ОТМЕНИТЬ", callback_data="wheel_cancel"))
        keyboard.adjust(1)
        
        # Сохраняем игру
        self.active_games[user_id] = {
            'balance': balance
        }
        
        await message.reply(
            f"🎰 ИГРА ВИЛИН 🎰\n\n"
            f"💰 Ваш баланс: {balance} MEM\n"
            f"🎯 Ставка: ВЕСЬ БАЛАНС\n"
            f"⚡ Результат: x2 или x0\n\n"
            f"🔥 Всё или ничего!\n"
            f"• Победа: баланс удваивается\n"
            f"• Проигрыш: баланс сгорает\n\n"
            f"Минимальный баланс: 100 MEM\n"
            f"Можно играть раз в минуту\n\n"
            f"Ваш выбор:",
            reply_markup=keyboard.as_markup()
        )
    
    async def handle_callback(self, callback: CallbackQuery):
        """Обработка нажатий на кнопки"""
        user_id = callback.from_user.id
        
        if user_id not in self.active_games:
            await callback.answer("Игра не найдена", show_alert=True)
            return
        
        game = self.active_games[user_id]
        
        if callback.data == "wheel_spin":
            # Крутим колесо
            await self.spin_wheel(callback, user_id, game['balance'])
        elif callback.data == "wheel_cancel":
            # Отменяем игру
            del self.active_games[user_id]
            await callback.message.edit_text("❌ Игра отменена")
            await callback.answer("Игра отменена")
    
    async def spin_wheel(self, callback: CallbackQuery, user_id: int, balance: int):
        """Крутить колесо"""
        # Устанавливаем кулдаун
        self.wheel_cooldowns[user_id] = time.time()
        
        # Определяем результат (50% шанс)
        won = random.choice([True, False])
        
        if won:
            # ПОБЕДА - удваиваем баланс
            new_balance = balance * 2
            await self.db.update_balance(user_id, balance)  # Прибавляем выигрыш
            
            result_text = (
                f"🎉 ПОБЕДА!\n\n"
                f"💰 Выигрыш: {balance} MEM\n"
                f"💎 Новый баланс: {new_balance} MEM\n\n"
                f"🔥 Баланс удвоен!\n"
                f"🎯 Можно играть снова через минуту"
            )
        else:
            # ПРОИГРЫШ - баланс сгорает
            await self.db.update_balance(user_id, -balance)  # Убираем весь баланс
            
            result_text = (
                f"😞 ПРОИГРЫШ\n\n"
                f"🔥 Потеряно: {balance} MEM\n"
                f"💸 Новый баланс: 0 MEM\n\n"
                f"😢 Баланс сгорел\n"
                f"🎯 Можно играть снова через минуту"
            )
        
        # Удаляем игру из активных
        del self.active_games[user_id]
        
        await callback.message.edit_text(result_text)
        await callback.answer("Игра завершена!")
    
    def get_rules(self) -> str:
        """Правила игры"""
        return (
            "🎰 ИГРА ВИЛИН 🎰\n\n"
            "📋 Правила:\n"
            "• Команда: `Вилин`\n"
            "• Минимальный баланс: 100 MEM\n"
            "• Ставка: ВЕСЬ баланс\n"
            "• Кулдаун: 1 минута\n\n"
            "🎯 Результаты:\n"
            "• Победа (50%): баланс ×2\n"
            "• Проигрыш (50%): баланс ×0\n\n"
            "🔥 Всё или ничего!"
        )
