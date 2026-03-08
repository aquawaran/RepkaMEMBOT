import random
import asyncio
from typing import Dict, List, Optional
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

class MinesGame:
    """Игра Мины - поиск алмазов на минном поле"""
    
    def __init__(self, database):
        self.db = database
        self.active_games: Dict[int, Dict] = {}  # user_id -> game_data
    
    async def start_game(self, message: Message, bet: int, mine_count: int) -> bool:
        """Начать игру в мины"""
        user_id = message.from_user.id
        user = await self.db.get_user(user_id)
        
        if not user or user['balance'] < bet:
            await message.reply("❌ Недостаточно MEM для ставки", reply_to_message_id=message.message_id)
            return False
        
        if bet < 100:
            await message.reply("❌ Минимальная ставка: 100 MEM", reply_to_message_id=message.message_id)
            return False
        
        if bet <= 0:
            await message.reply("❌ Ставка должна быть больше 0", reply_to_message_id=message.message_id)
            return False
        
        if mine_count < 2 or mine_count > 20:
            await message.reply("❌ Количество мин: от 2 до 20", reply_to_message_id=message.message_id)
            return False
        
        # Списываем ставку
        await self.db.update_balance(user_id, -bet)
        
        # Создаем игровое поле 5x5
        field_size = 5
        total_cells = field_size * field_size
        
        # Генерируем позиции мин и алмазов
        diamonds_count = total_cells - mine_count  # Остальные - алмазы
        
        positions = list(range(total_cells))
        random.shuffle(positions)
        
        mine_positions = set(positions[:mine_count])
        diamond_positions = set(positions[mine_count:])  # Все оставшиеся - алмазы
        
        # Рассчитываем базовый множитель в зависимости от количества мин
        # Более реалистичные коэффициенты
        if mine_count == 1:
            base_multiplier = 1.05
        elif mine_count == 2:
            base_multiplier = 1.10
        elif mine_count == 3:
            base_multiplier = 1.20
        elif mine_count == 4:
            base_multiplier = 1.35
        elif mine_count == 5:
            base_multiplier = 1.55
        elif mine_count == 6:
            base_multiplier = 1.80
        elif mine_count == 7:
            base_multiplier = 2.10
        elif mine_count == 8:
            base_multiplier = 2.45
        elif mine_count == 9:
            base_multiplier = 2.85
        elif mine_count == 10:
            base_multiplier = 3.30
        elif mine_count == 11:
            base_multiplier = 3.80
        elif mine_count == 12:
            base_multiplier = 4.35
        elif mine_count == 13:
            base_multiplier = 4.95
        elif mine_count == 14:
            base_multiplier = 5.60
        elif mine_count == 15:
            base_multiplier = 6.30
        else:
            # Для 16-20 мин
            base_multiplier = 7.00 + (mine_count - 15) * 0.80
        
        # Сохраняем игру
        self.active_games[user_id] = {
            'field_size': field_size,
            'mine_positions': mine_positions,
            'diamond_positions': diamond_positions,
            'revealed': set(),
            'bet': bet,
            'multiplier': 1.0,
            'found_diamonds': 0,
            'game_over': False,
            'mine_count': mine_count,
            'base_multiplier': base_multiplier
        }
        
        # Отправляем игровое поле
        await self._send_field(message, user_id)
        return True
    
    async def _send_field(self, message: Message, user_id: int):
        """Отправить игровое поле"""
        game = self.active_games.get(user_id)
        if not game:
            return
        
        field_size = game['field_size']
        revealed = game['revealed']
        mine_positions = game['mine_positions']
        diamond_positions = game['diamond_positions']
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        for row in range(field_size):
            buttons = []
            for col in range(field_size):
                cell_num = row * field_size + col
                
                if cell_num in revealed:
                    if cell_num in mine_positions:
                        buttons.append(InlineKeyboardButton(text="💣", callback_data=f"mines_reveal_{cell_num}"))
                    elif cell_num in diamond_positions:
                        buttons.append(InlineKeyboardButton(text="💎", callback_data=f"mines_reveal_{cell_num}"))
                else:
                    buttons.append(InlineKeyboardButton(text="❓", callback_data=f"mines_reveal_{cell_num}"))
            
            builder.row(*buttons)
        
        # Добавляем кнопки управления
        if game['found_diamonds'] > 0 and not game['game_over']:
            current_win = int(game['bet'] * game['multiplier'])
            builder.row(
                InlineKeyboardButton(text=f"💰 Забрать {current_win} MEM", callback_data="mines_cashout")
            )
        
        # Статус игры
        status_text = f"💎 Мины\n\n"
        status_text += f"📊 Ставка: {game['bet']} MEM\n"
        status_text += f"💰 Текущий выигрыш: {int(game['bet'] * game['multiplier'])} MEM\n"
        status_text += f"🔢 Множитель: x{game['multiplier']:.2f}\n"
        status_text += f"💎 Найдено алмазов: {game['found_diamonds']}\n\n"
        status_text += "Нажимайте на клетки чтобы открыть их!"
        
        try:
            await message.edit_text(status_text, reply_markup=builder.as_markup())
        except:
            await message.answer(status_text, reply_markup=builder.as_markup())
    
    async def handle_cell_click(self, callback, user_id: int, cell_num: int):
        """Обработать нажатие на клетку"""
        game = self.active_games.get(user_id)
        if not game or game['game_over']:
            await callback.answer("Игра завершена", show_alert=True)
            return
        
        if cell_num in game['revealed']:
            await callback.answer("Эта клетка уже открыта", show_alert=True)
            return
        
        game['revealed'].add(cell_num)
        
        if cell_num in game['mine_positions']:
            # Попал на мину - игра окончена
            game['game_over'] = True
            await self._game_over(callback, user_id, won=False)
        elif cell_num in game['diamond_positions']:
            # Нашел алмаз - пересчитываем итоговый множитель как в реальных играх
            game['found_diamonds'] += 1
            
            # Расчет как в реальных играх (Stakes, BC.Game, etc.)
            opened_cells = len(game['revealed'])
            total_cells = game['field_size'] * game['field_size']
            mine_count = len(game['mine_positions'])
            
            # Формула: (всего клеток / (всего клеток - количество мин)) ^ открытые_клетки
            # Но более точная формула для пошаговой игры:
            remaining_cells = total_cells - opened_cells
            remaining_mines = mine_count
            
            # Коэффициент = произведение вероятностей на каждом шаге
            # Вероятность на каждом шаге: (оставшиеся клетки - мины) / оставшиеся клетки
            if remaining_cells > 0:
                # Общий коэффициент для всех открытых клеток
                probability = 1.0
                for i in range(opened_cells):
                    step_cells = total_cells - i
                    step_mines = mine_count
                    step_probability = (step_cells - step_mines) / step_cells
                    probability *= step_probability
                
                if probability > 0:
                    game['multiplier'] = 1.0 / probability
                else:
                    game['multiplier'] = 999.0  # Максимальный коэффициент
            else:
                game['multiplier'] = 999.0
            
            await callback.answer(f"💎 Алмаз! Множитель x{game['multiplier']:.2f}")
            # Небольшая задержка перед обновлением поля
            import asyncio
            await asyncio.sleep(0.1)
            await self._send_field(callback.message, user_id)
        else:
            # Пустая клетка
            await callback.answer("⬜ Пусто")
            await self._send_field(callback.message, user_id)
    
    async def handle_cashout(self, callback, user_id: int):
        """Забрать выигрыш"""
        game = self.active_games.get(user_id)
        if not game or game['game_over'] or game['found_diamonds'] == 0:
            await callback.answer("Нельзя забрать выигрыш", show_alert=True)
            return
        
        win_amount = int(game['bet'] * game['multiplier'])
        await self.db.update_balance(user_id, win_amount)
        await self.db.update_daily_winnings(user_id, win_amount - game['bet'])
        
        game['game_over'] = True
        del self.active_games[user_id]
        
        await callback.message.edit_text(
            f"🎉 **Выигрыш забран!**\n\n"
            f"💰 Выигрыш: {win_amount} MEM\n"
            f"📊 Множитель: x{game['multiplier']:.2f}\n"
            f"💎 Найдено алмазов: {game['found_diamonds']}"
        )
    
    async def _game_over(self, callback, user_id: int, won: bool):
        """Завершить игру"""
        game = self.active_games[user_id]
        
        if won:
            win_amount = int(game['bet'] * game['multiplier'])
            await self.db.update_balance(user_id, win_amount)
            await self.db.update_daily_winnings(user_id, win_amount - game['bet'])
            result_text = f"🎉 Победа!\n\n💰 Выигрыш: {win_amount} MEM"
        else:
            result_text = f"💥 Game Over!\n\n💸 Проигрыш: {game['bet']} MEM"
        
        # Показываем все мины и алмазы
        field_size = game['field_size']
        builder = InlineKeyboardBuilder()
        
        for row in range(field_size):
            buttons = []
            for col in range(field_size):
                cell_num = row * field_size + col
                
                if cell_num in game['mine_positions']:
                    buttons.append(InlineKeyboardButton(text="💣", callback_data="disabled"))
                elif cell_num in game['diamond_positions']:
                    buttons.append(InlineKeyboardButton(text="💎", callback_data="disabled"))
            
            builder.row(*buttons)
        
        del self.active_games[user_id]
        
        await callback.message.edit_text(result_text, reply_markup=builder.as_markup())
    
    def get_rules(self) -> str:
        """Получить правила игры"""
        rules = "💎 МИНЫ\n\n"
        rules += "📜 Правила:\n"
        rules += "• Минимальная ставка: 100 MEM\n"
        rules += "• Поле 5x5 с алмазами и бомбами\n"
        rules += "• Нужно найти алмазы, избегая бомб\n"
        rules += "• Можно забрать выигрыш после первого алмаза\n\n"
        rules += "💰 Множители:\n"
        rules += "• Каждый найденный алмаз: x1.25\n"
        rules += "• Множители умножаются: 1.00 → 1.25 → 1.56 → ...\n\n"
        rules += "🎮 Команда: Мины [ставка]"
        
        return rules
