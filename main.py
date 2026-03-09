import asyncio
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from json_database import JSONDatabase
from games.mines import MinesGame
from games.slots import SlotsGame
from games.trade_game import TradeGame
from games.wheel import WheelGame
from games.roulette import init_roulette

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 5439940299))  # Твой ID по умолчанию
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@InitialNFT")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = JSONDatabase()

# Инициализация игр
mines_game = MinesGame(db)
slots_game = SlotsGame(db)
trade_game = TradeGame(db)
wheel_game = WheelGame(db)
roulette_game = init_roulette(db)

# Кулдауны для пользователей
user_cooldowns: Dict[int, float] = {}
bonus_cooldowns: Dict[int, float] = {}
COOLDOWN_SECONDS = 1.75
BONUS_COOLDOWN_HOURS = 24

# Глобальный кулдаун - блокирует все команды пользователя на 3 секунды
global_cooldowns: Dict[int, float] = {}

# Клавиатуры
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Баланс"), KeyboardButton(text="Банк")],
            [KeyboardButton(text="Профиль"), KeyboardButton(text="Инвентарь")],
            [KeyboardButton(text="Топ"), KeyboardButton(text="Бонус")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_help_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 ОСНОВНОЕ", callback_data="help_basic")],
            [InlineKeyboardButton(text="🎮 ИГРЫ", callback_data="help_games")]
        ]
    )
    return keyboard

def normalize_text(text: str) -> str:
    """Заменяет ё на е и убирает эмодзи для удобства пользователей"""
    # Заменяем ё на е
    text = text.replace('ё', 'е').replace('Ё', 'Е')
    # Убираем эмодзи (сохраняем буквы, цифры, пробелы)
    text = re.sub(r'[^\w\sа-яА-ЯёЁ]', '', text)
    # Убираем лишние пробелы
    text = ' '.join(text.split())
    return text

def parse_amount(amount_str: str, user_balance: int = 0) -> Optional[int]:
    """Парсит сумму с поддержкой К, М, и ВСЁ"""
    amount_str = normalize_text(amount_str.upper().strip())
    
    if amount_str == "ВСЕ" or amount_str == "ALL":
        return user_balance
    
    # Убираем нечисловые символы кроме К и М
    clean_str = ""
    for char in amount_str:
        if char.isdigit() or char in "КМ":
            clean_str += char
    
    if not clean_str:
        return None
    
    # Парсим множители
    if clean_str.endswith("К"):
        try:
            return int(clean_str[:-1]) * 1000
        except:
            return None
    elif clean_str.endswith("М"):
        try:
            return int(clean_str[:-1]) * 1000000
        except:
            return None
    else:
        try:
            return int(clean_str)
        except:
            return None
def check_cooldown(user_id: int) -> bool:
    """Проверить, может ли пользователь использовать команду"""
    current_time = time.time()
    
    # Проверяем кулдаун
    if user_id in user_cooldowns:
        time_diff = current_time - user_cooldowns[user_id]
        if time_diff < COOLDOWN_SECONDS:
            # Строго игнорируем команды в кулдауне
            return False
    
    # Обновляем время только после успешной проверки
    user_cooldowns[user_id] = current_time
    return True

# Проверка забаненности пользователя
async def is_user_banned(user_id: int) -> bool:
    user = await db.get_user(user_id)
    return user and user.get('is_banned', False)

# Получение пользователя по сообщению
async def get_target_user(message: Message) -> Optional[int]:
    """Получение ID пользователя из ответа на сообщение или текста"""
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    
    # Если указан username
    if message.text and message.text.startswith("@"):
        username = message.text[1:].split()[0]
        # Здесь нужно будет реализовать поиск по username в БД
        # Для упрощения пока вернем None
        return None
    
    return None

# Обработчик /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🏦 Банк")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎒 Инвентарь")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="💎 Бонус")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    
    channel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 Наш канал", url="https://t.me/InitialNFT")]
        ]
    )
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Добро пожаловать в MEM!\n\n"
        f"🎮 Здесь ты можешь:\n"
        f"• Играть в игры и зарабатывать MEM\n"
        f"• Общаться с другими игроками\n"
        f"• Участвовать в топах и турнирах\n\n"
        f"🪙 Валюта: MEM\n"
        f"📝 Все команды пишутся без слеша на русском языке\n\n"
        f"Начальный бонус: 1000 MEM 💰",
        reply_markup=keyboard
    )
    
    # Отправляем отдельное сообщение с кнопкой канала
    await message.answer(
        "📺 Подпишись на наш канал @InitialNFT чтобы быть в курсе новостей!",
        reply_markup=channel_keyboard
    )

# Обработчик текстовых сообщений
@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    
    # СТРОГИЙ КУЛДАУН - ПРОВЕРКА В САМОМ НАЧАЛЕ
    current_time = time.time()
    
    # Админ всегда без кулдауна
    if user_id == ADMIN_ID:
        print(f"👑 АДМИН без кулдауна: {user_id}")
    else:
        if user_id in global_cooldowns:
            time_diff = current_time - global_cooldowns[user_id]
            if time_diff < COOLDOWN_SECONDS:
                print(f"❌ ЗАБЛОКИРОВАНО для {user_id}: прошло {time_diff:.2f} сек из {COOLDOWN_SECONDS}")
                return  # ПОЛНЫЙ БЛОК
        
        # Устанавливаем кулдаун
        global_cooldowns[user_id] = current_time
        print(f"✅ РАЗРЕШЕНО для {user_id}")
    
    if await is_user_banned(user_id):
        return
    
    text = normalize_text(message.text.lower().strip())
    user_id = message.from_user.id
    
    # Убедимся что пользователь есть в БД
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    # Основные команды
    if text == "б/баланс" or text == "баланс" or text == "б":
        await handle_balance(message)
    elif text == "банк":
        await handle_bank(message)
    elif text == "профиль":
        await handle_profile(message)
    elif text == "инвентарь":
        await handle_inventory(message)
    elif text == "топ":
        await handle_top(message)
    elif text == "топ банки":
        await handle_top_banks(message)
    elif text == "лидерборд":
        await handle_leaderboard(message)
    elif text == "бонус":
        await handle_bonus(message)
    elif text == "помощь":
        await handle_help(message)
    elif text == "игроки":
        await handle_players(message)
    elif text == "пинг":
        await handle_ping(message)
    elif text == "ласт":
        await handle_last(message)
    elif text.startswith("дать "):
        await handle_give(message)
    elif text.startswith("банк снять "):
        await handle_bank_withdraw(message)
    elif text.startswith("банк пополнить ") or text.startswith("банк положить "):
        await handle_bank_deposit(message)
    elif text == "сменить аватарку":
        await handle_change_avatar(message)
    elif text == "удалить аватарку":
        await handle_delete_avatar(message)
    elif text == "б закрыть":
        await handle_close_profile(message)
    elif text == "б открыть":
        await handle_open_profile(message)
    # Альтернативные варианты с "е" вместо "ё"
    elif text == "смена аватарки":
        await handle_change_avatar(message)
    elif text == "удалениe аватарки":
        await handle_delete_avatar(message)
    elif text == "б закрыт":
        await handle_close_profile(message)
    elif text == "б открыт":
        await handle_open_profile(message)
    
    # Игровые команды
    elif text.startswith("мины"):
        try:
            parts = text.split()
            
            # Обрабатываем разные случаи
            if text == "мины":
                await message.reply("💣 Использование: Мины [ставка] [количество мин]\n\n📌 Примеры:\n• Мины 1000 3\n• Мины 500к 5\n• Мины 2м 10\n\n🎯 Количество мин: от 1 до 24", reply_to_message_id=message.message_id)
                return
            
            if len(parts) == 2:
                # Случай: "мины 1000" - не хватает количества мин
                await message.reply("💣 Укажите количество мин!\n\n📌 Использование: Мины [ставка] [количество мин]\n🎯 Количество мин: от 1 до 24", reply_to_message_id=message.message_id)
                return
            
            if len(parts) == 3:
                user = await db.get_user(message.from_user.id)
                if user:
                    bet = parse_amount(parts[1], user['balance'])
                    mine_count = int(parts[2])
                    
                    # Проверяем диапазон мин
                    if mine_count < 1 or mine_count > 24:
                        await message.reply("❌ Количество мин должно быть от 1 до 24", reply_to_message_id=message.message_id)
                        return
                    
                    if bet is not None:
                        # Проверяем что ставка не больше баланса
                        if bet <= user['balance'] and bet > 0:
                            await mines_game.start_game(message, bet, mine_count)
                        else:
                            await message.reply("❌ Недостаточно средств или неверная сумма", reply_to_message_id=message.message_id)
                    else:
                        await message.reply("❌ Неверная сумма", reply_to_message_id=message.message_id)
                else:
                    await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
            else:
                await message.reply("💣 Использование: Мины [ставка] [количество мин]\n\n📌 Примеры:\n• Мины 1000 3\n• Мины 500к 5\n• Мины 2м 10\n\n🎯 Количество мин: от 1 до 24", reply_to_message_id=message.message_id)
        except (ValueError, IndexError):
            await message.reply("💣 Использование: Мины [ставка] [количество мин]\n\n📌 Примеры:\n• Мины 1000 3\n• Мины 500к 5\n• Мины 2м 10\n\n🎯 Количество мин: от 1 до 24", reply_to_message_id=message.message_id)
    elif text.startswith("слоты "):
        try:
            parts = text.split()
            if len(parts) >= 2:
                user = await db.get_user(message.from_user.id)
                if user:
                    bet = parse_amount(parts[1], user['balance'])
                    if bet is not None:
                        # Проверяем что ставка не больше баланса
                        if bet <= user['balance'] and bet > 0:
                            await slots_game.play(message, bet)
                        else:
                            await message.reply("❌ Недостаточно средств или неверная сумма", reply_to_message_id=message.message_id)
                    else:
                        await message.reply("❌ Неверная сумма", reply_to_message_id=message.message_id)
                else:
                    await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
            else:
                await message.reply("❌ Использование: Слоты [ставка]", reply_to_message_id=message.message_id)
        except (ValueError, IndexError):
            await message.reply("❌ Использование: Слоты [ставка]", reply_to_message_id=message.message_id)
    elif text.startswith("трейдап "):
        try:
            # Проверяем включена ли игра
            game_settings = await db.get_game_settings()
            if not game_settings.get("trade", True):
                await message.reply("🚫 Игра Трейд временно отключена", reply_to_message_id=message.message_id)
                return
                
            parts = text.split()
            if len(parts) >= 2:
                user = await db.get_user(message.from_user.id)
                if user:
                    bet = parse_amount(parts[1], user['balance'])
                    if bet is not None:
                        # Проверяем что ставка не больше баланса
                        if bet <= user['balance'] and bet > 0:
                            await trade_game.start_game(message, bet, "up")
                        else:
                            await message.reply("❌ Недостаточно средств или неверная сумма", reply_to_message_id=message.message_id)
                    else:
                        await message.reply("❌ Неверная сумма", reply_to_message_id=message.message_id)
                else:
                    await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
            else:
                await message.reply("❌ Использование: Трейдап [ставка]", reply_to_message_id=message.message_id)
        except (ValueError, IndexError):
            await message.reply("❌ Использование: Трейдап [ставка]", reply_to_message_id=message.message_id)
    elif text.startswith("трейдовн "):
        try:
            # Проверяем включена ли игра
            game_settings = await db.get_game_settings()
            if not game_settings.get("trade", True):
                await message.reply("🚫 Игра Трейд временно отключена", reply_to_message_id=message.message_id)
                return
                
            parts = text.split()
            if len(parts) >= 2:
                user = await db.get_user(message.from_user.id)
                if user:
                    bet = parse_amount(parts[1], user['balance'])
                    if bet is not None:
                        # Проверяем что ставка не больше баланса
                        if bet <= user['balance'] and bet > 0:
                            await trade_game.start_game(message, bet, "down")
                        else:
                            await message.reply("❌ Недостаточно средств или неверная сумма", reply_to_message_id=message.message_id)
                    else:
                        await message.reply("❌ Неверная сумма", reply_to_message_id=message.message_id)
                else:
                    await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
            else:
                await message.reply("❌ Использование: Трейдовн [ставка]", reply_to_message_id=message.message_id)
        except (ValueError, IndexError):
            await message.reply("❌ Использование: Трейдовн [ставка]", reply_to_message_id=message.message_id)
    elif text == "вилин":
        await wheel_game.start_game(message)
    elif text == "мойид":
        await handle_my_id(message)
    
    # Команды рулетки (только в чатах)
    elif message.chat.type != "private":
        if text.startswith("рулетка "):
            # Проверяем включена ли игра
            game_settings = await db.get_game_settings()
            if not game_settings.get("roulette", True):
                await message.reply("🚫 Игра Рулетка временно отключена", reply_to_message_id=message.message_id)
                return
                
            try:
                parts = text.split()
                if len(parts) >= 3:
                    user = await db.get_user(message.from_user.id)
                    if user:
                        bet = parse_amount(parts[1], user['balance'])
                        if bet is not None:
                            if bet <= user['balance'] and bet > 0:
                                # Получаем все значения ставок (все что после ставки)
                                bet_values = parts[2:]  # ['1', '3', '5', '12-16', '17-19', '27']
                                
                                await roulette_game.place_bet(message, bet, bet_values)
                            else:
                                await message.reply("❌ Недостаточно средств или неверная сумма", reply_to_message_id=message.message_id)
                        else:
                            await message.reply("❌ Неверная сумма", reply_to_message_id=message.message_id)
                    else:
                        await message.reply("❌ Пользователь не найден", reply_to_message_id=message.message_id)
                else:
                    await message.reply("❌ Использование: Рулетка [ставка] [ставки...]\n\n📋 Примеры:\n• Рулетка 1000 7\n• Рулетка 1000 красный\n• Рулетка 1000 10-20\n• Рулетка 1000 odd\n• Рулетка 1000 1 3 5 12-16 17-19 27", reply_to_message_id=message.message_id)
            except (ValueError, IndexError):
                await message.reply("❌ Использование: Рулетка [ставка] [ставки...]\n\n📋 Примеры:\n• Рулетка 1000 7\n• Рулетка 1000 красный\n• Рулетка 1000 10-20\n• Рулетка 1000 odd\n• Рулетка 1000 1 3 5 12-16 17-19 27", reply_to_message_id=message.message_id)
        elif text == "го":
            # Проверяем включена ли игра
            game_settings = await db.get_game_settings()
            if not game_settings.get("roulette", True):
                await message.reply("🚫 Игра Рулетка временно отключена", reply_to_message_id=message.message_id)
                return
                
            await roulette_game.start_round(message)
        elif text == "лог":
            await roulette_game.show_history(message)
        elif text == "рулетка":
            await roulette_game.show_help(message)
    
    # Админ команды
    elif user_id == ADMIN_ID:
        if text.startswith("экспорт"):
            await handle_export_db(message)
        elif text.startswith("инициализбд"):
            await handle_init_db(message)
        elif text.startswith("выдать"):
            await handle_give_admin(message)
        elif text.startswith("забрать"):
            await handle_take_admin(message)
        elif text.startswith("бан"):
            await handle_ban_user(message)
        elif text.startswith("разбан"):
            await handle_unban_user(message)
        elif text.startswith("игры"):
            await handle_game_control(message)
        elif text == "игроконтроль" or text == "игроконтроль":
            await handle_game_control(message)

# Обработчик callback кнопок
@dp.callback_query(F.data.startswith("profile_"))
async def handle_profile_callback(callback: CallbackQuery):
    """Обработчик кнопок профилей из топов"""
    try:
        user_id = int(callback.data.split("_")[1])
        user = await db.get_user(user_id)
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Создаем текст профиля
        profile_text = f"👤 Профиль пользователя\n\n"
        profile_text += f"🆔 ID: {user['user_id']}\n"
        profile_text += f"👤 Имя: {user['first_name']}\n"
        
        # Добавляем баланс и банк только если профиль открыт
        if not user.get('profile_closed', False):
            profile_text += f"💰 Баланс: {user['balance']} MEM\n"
            profile_text += f"🏦 Банк: {user['bank_balance']} MEM\n"
        
        profile_text += f"📅 Регистрация: {user['registration_date']}\n"
        
        # Добавляем аватарку если есть
        if user.get('avatar_path'):
            try:
                await callback.message.answer_photo(user['avatar_path'], caption=f"<blockquote>{profile_text}</blockquote>", parse_mode="HTML")
            except:
                await callback.message.answer(f"<blockquote>{profile_text}</blockquote>", parse_mode="HTML")
        else:
            await callback.message.answer(f"<blockquote>{profile_text}</blockquote>", parse_mode="HTML")
        
        await callback.answer("✅ Профиль открыт")
        
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка при открытии профиля", show_alert=True)

# Обработчик callback для игры Вилин
@dp.callback_query(F.data.startswith("wheel_"))
async def handle_wheel_callback(callback: CallbackQuery):
    """Обработчик кнопок игры Вилин"""
    await wheel_game.handle_callback(callback)

# Обработчики команд
async def handle_balance(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.reply(f"💰 Ваш баланс: {user['balance']} MEM")

async def handle_bank(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.reply(f"🏦 Баланс банка: {user['bank_balance']} MEM")

async def handle_profile(message: Message):
    target_id = await get_target_user(message) or message.from_user.id
    user = await db.get_user(target_id)
    
    if not user:
        await message.reply("❌ Пользователь не найден")
        return
    
    # Проверяем закрыт ли профиль
    if target_id != message.from_user.id and user.get('profile_closed', False):
        await message.reply("🔒 Профиль этого пользователя закрыт")
        return
    
    profile_text = f"👤 Профиль пользователя\n\n"
    profile_text += f"🆔 ID: {user['user_id']}\n"
    profile_text += f"👤 Имя: {user['first_name']}\n"
    
    # Добавляем баланс и банк только если профиль открыт
    if not user.get('profile_closed', False):
        profile_text += f"💰 Баланс: {user['balance']} MEM\n"
        profile_text += f"🏦 Банк: {user['bank_balance']} MEM\n"
    
    profile_text += f"📅 Регистрация: {user['registration_date']}\n"
    
    # Добавляем аватарку если есть
    if user.get('avatar_path'):
        try:
            await message.reply_photo(user['avatar_path'], caption=f"<blockquote>{profile_text}</blockquote>", parse_mode="HTML")
            return
        except:
            pass  # Если не удалось отправить фото, продолжаем без аватарки
    
    await message.reply(f"<blockquote>{profile_text}</blockquote>", parse_mode="HTML")

async def handle_inventory(message: Message):
    await message.reply("🎒 Ваш инвентарь:\n\nПусто (скоро появятся предметы)")

async def handle_top(message: Message):
    top_users = await db.get_top_users(10)
    
    text = "🏆 Топ 10 игроков по балансу\n\n"
    
    # Создаем инлайн кнопки для каждого пользователя
    keyboard = InlineKeyboardMarkup()
    buttons = []
    
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user['first_name']} - {user['balance']} MEM\n"
        # Добавляем кнопку для перехода на профиль
        buttons.append([InlineKeyboardButton(
            text=f"👤 {i}. {user['first_name']}", 
            url=f"tg://user?id={user['user_id']}"
        )])
    
    if not top_users:
        text += "Пока нет игроков в топе"
    
    if buttons:
        keyboard.inline_keyboard = buttons
        await message.reply(text, reply_markup=keyboard)
    else:
        await message.reply(text)

async def handle_top_banks(message: Message):
    top_banks = await db.get_top_banks(10)
    
    text = "💎 Топ 10 банков\n\n"
    
    # Создаем инлайн кнопки для каждого пользователя
    keyboard = InlineKeyboardMarkup()
    buttons = []
    
    for i, user in enumerate(top_banks, 1):
        text += f"{i}. {user['first_name']} - {user['bank_balance']} MEM\n"
        # Добавляем кнопку для перехода на профиль
        buttons.append([InlineKeyboardButton(
            text=f"👤 {i}. {user['first_name']}", 
            url=f"tg://user?id={user['user_id']}"
        )])
    
    if not top_banks:
        text += "Пока нет игроков в топе банков"
    
    if buttons:
        keyboard.inline_keyboard = buttons
        await message.reply(text, reply_markup=keyboard)
    else:
        await message.reply(text)

async def handle_leaderboard(message: Message):
    leaderboard = await db.get_leaderboard(5)
    
    text = "🏅 Лидерборд дня\n\n"
    
    # Создаем инлайн кнопки для каждого пользователя
    keyboard = InlineKeyboardMarkup()
    buttons = []
    
    for i, user in enumerate(leaderboard, 1):
        text += f"{i}. {user['first_name']} - {user['daily_winnings']} MEM\n"
        # Добавляем кнопку для перехода на профиль
        buttons.append([InlineKeyboardButton(
            text=f"👤 {i}. {user['first_name']}", 
            url=f"tg://user?id={user['user_id']}"
        )])
    
    if not leaderboard:
        text += "Пока нет победителей сегодня"
    
    if buttons:
        keyboard.inline_keyboard = buttons
        await message.reply(text, reply_markup=keyboard)
    else:
        await message.reply(text)

async def handle_bonus(message: Message):
    user_id = message.from_user.id
    current_time = time.time()
    
    # Проверяем кулдаун на бонус
    if user_id in bonus_cooldowns:
        hours_passed = (current_time - bonus_cooldowns[user_id]) / 3600
        if hours_passed < BONUS_COOLDOWN_HOURS:
            remaining_hours = BONUS_COOLDOWN_HOURS - hours_passed
            await message.reply(f"⏳ Бонус можно получить через {int(remaining_hours)} часов")
            return
    
    # Проверяем подписку на канал
    try:
        # Канал для проверки подписки
        channel_member = await bot.get_chat_member("@InitialNFT", user_id)
        if channel_member.status == "left":
            # Создаем кнопку для перехода на канал
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📺 Перейти на канал", url="https://t.me/InitialNFT")]
                ]
            )
            await message.reply("❌ Для получения бонуса нужно подписаться на канал @InitialNFT", reply_markup=keyboard)
            return
    except:
        # Если не удалось проверить подписку, всё равно выдаем бонус
        pass
    
    # Выдаем бонус
    bonus = random.randint(700, 7000)
    await db.update_balance(user_id, bonus)
    bonus_cooldowns[user_id] = current_time
    
    await message.reply(f"🎁 Бонус получен!\n💰 +{bonus} MEM\n\nБонус можно получить раз в 24 часа")

async def handle_help(message: Message):
    await message.answer("📚 Выберите раздел помощи:", reply_markup=get_help_keyboard())

async def handle_players(message: Message):
    """Показать количество зарегистрированных игроков"""
    # Получаем всех пользователей
    all_users = await db.get_top_users(10000)  # Большой лимит чтобы получить всех
    total_players = len(all_users)
    
    # Считаем активных (не забаненных)
    active_players = len([u for u in all_users if not u.get('is_banned', False)])
    
    text = f"👥 Статистика игроков\n\n"
    text += f"📊 Всего зарегистрировано: {total_players} игроков\n"
    text += f"✅ Активных игроков: {active_players}\n"
    
    if total_players > active_players:
        banned_players = total_players - active_players
        text += f"🚫 Забанено: {banned_players} игроков"
    
    await message.reply(text)

async def handle_ping(message: Message):
    """Измерить пинг до Telegram API"""
    start_time = time.time()
    
    # Отправляем временное сообщение чтобы измерить время ответа
    temp_message = await message.reply("🏓 Проверка пинга...")
    
    # Вычисляем время
    end_time = time.time()
    ping_ms = int((end_time - start_time) * 1000)
    
    # Редактируем сообщение с результатом
    await temp_message.edit_text(f"🏓 Пинг: {ping_ms} мс")

async def handle_last(message: Message):
    """Показать последние 10 игр пользователя"""
    user_id = message.from_user.id
    game_history = await db.get_game_history(user_id)
    
    if not game_history:
        await message.reply("<blockquote>🎮 ИСТОРИЯ ИГР\n\nУ вас пока нет сыгранных игр</blockquote>", parse_mode="HTML")
        return
    
    text = "🎮 ИСТОРИЯ ИГР\n\n"
    
    for i, game in enumerate(game_history[:10], 1):
        game_name = game["game"]
        bet = game["bet"]
        result = game["result"]
        win_amount = game.get("win_amount", 0)
        
        if result == "win":
            text += f"{i}. 🟢 {game_name} | Ставка: {bet} MEM | Выигрыш: +{win_amount} MEM\n"
        else:
            text += f"{i}. 🔴 {game_name} | Ставка: {bet} MEM | Проигрыш: -{bet} MEM\n"
    
    await message.reply(f"<blockquote>{text}</blockquote>", parse_mode="HTML")

async def handle_give(message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌ Использование: дать [сумма]")
            return
        
        sender_user = await db.get_user(message.from_user.id)
        if not sender_user:
            await message.reply("❌ Пользователь не найден")
            return
        
        amount = parse_amount(parts[1], sender_user['balance'])
        if amount is None:
            await message.reply("❌ Неверная сумма")
            return
        
        if amount <= 0:
            await message.reply("❌ Сумма должна быть положительной")
            return
        
        if sender_user['balance'] < amount:
            await message.reply("❌ Недостаточно MEM")
            return
        
        target_id = await get_target_user(message)
        
        if not target_id:
            await message.reply("❌ Ответьте на сообщение пользователя")
            return
        
        # Проверяем что не пытаются перевести боту
        if target_id == message.bot.id:
            await message.reply("❌ Нельзя переводить MEM боту")
            return
        
        if target_id == message.from_user.id:
            await message.reply("❌ Нельзя перевести самому себе")
            return
        
        # Выполняем перевод
        await db.update_balance(message.from_user.id, -amount)
        await db.update_balance(target_id, amount)
        
        await message.reply(f"✅ Переведено {amount} MEM")
    except ValueError:
        await message.reply("❌ Неверная сумма")

async def handle_bank_withdraw(message: Message):
    try:
        amount = int(message.text.split()[2])
        user = await db.get_user(message.from_user.id)
        
        if user['bank_balance'] >= amount:
            # Комиссия 5% на вывод
            commission = int(amount * 0.05)
            final_amount = amount - commission
            
            await db.update_bank_balance(message.from_user.id, -amount)
            await db.update_balance(message.from_user.id, final_amount)
            
            if commission > 0:
                await message.reply(f"✅ Снято {final_amount} MEM с банка\n💸 Комиссия: {commission} MEM (5%)")
            else:
                await message.reply(f"✅ Снято {final_amount} MEM с банка")
        else:
            await message.reply("❌ Недостаточно средств в банке")
    except (ValueError, IndexError):
        await message.reply("❌ Использование: Банк снять [сумма]")

async def handle_bank_deposit(message: Message):
    try:
        amount = int(message.text.split()[2])
        user = await db.get_user(message.from_user.id)
        
        if user['balance'] >= amount:
            await db.update_balance(message.from_user.id, -amount)
            await db.update_bank_balance(message.from_user.id, amount)
            await message.reply(f"✅ Положено {amount} MEM в банк")
        else:
            await message.reply("❌ Недостаточно средств")
    except (ValueError, IndexError):
        await message.reply("❌ Использование: Банк пополнить [сумма]")

async def handle_export_db(message: Message):
    # Проверка на админа
    if message.from_user.id != ADMIN_ID:
        await message.reply(f"❌ Доступ запрещен. Твой ID: {message.from_user.id}, ADMIN_ID: {ADMIN_ID}")
        return
        
    try:
        # Проверяем существование файла
        import os
        db_path = "bot_data.json"
        
        if not os.path.exists(db_path):
            await message.reply("❌ Файл базы данных не найден")
            return
        
        # Проверяем размер файла
        file_size = os.path.getsize(db_path)
        if file_size == 0:
            await message.reply("❌ Файл базы данных пуст")
            return
        
        # Детальная диагностика базы данных
        try:
            # Получаем статистику
            users = await db.get_top_users(1000)  # Все пользователи
            settings = await db.get_game_settings()
            
            # Считаем статистику
            total_users = len(users)
            active_users = len([u for u in users if not u.get("is_banned", False)])
            total_balance = sum(u.get("balance", 0) for u in users)
            banned_users = total_users - active_users
            
            # Формируем отчет
            report = f"📊 ДИАГНОСТИКА JSON БАЗЫ ДАННЫХ\n\n"
            report += f"📁 Размер файла: {file_size} байт\n"
            report += f"� Всего пользователей: {total_users}\n"
            report += f"✅ Активные пользователи: {active_users}\n"
            report += f"🚫 Забаненные: {banned_users}\n"
            report += f"💰 Общий баланс: {total_balance} MEM\n\n"
            report += f"🎮 Настройки игр:\n"
            for game, enabled in settings.items():
                status = "✅" if enabled else "🚫"
                report += f"  {status} {game}\n"
            report += f"\n📅 Последнее сохранение: {db.get_last_save()}\n"
            
            await message.reply(report)
            
            # Читаем файл в память
            with open(db_path, "rb") as db_file:
                file_data = db_file.read()
            
            # Отправляем как документ с правильным MIME типом
            from aiogram.types import BufferedInputFile
            document = BufferedInputFile(
                file=file_data,
                filename=f"bot_database_{int(os.path.getmtime(db_path))}.json"
            )
            
            await message.reply_document(
                document,
                caption=f"📊 JSON база данных бота\n📁 Размер: {file_size} байт\n👥 Пользователей: {total_users}"
            )
            
        except Exception as e:
            await message.reply(f"❌ Ошибка при чтении базы данных: {str(e)}")
            
    except FileNotFoundError:
        await message.reply("❌ Файл базы данных не найден")
    except PermissionError:
        await message.reply("❌ Нет доступа к файлу базы данных")
    except Exception as e:
        await message.reply(f"❌ Ошибка при экспорте: {str(e)}")

async def handle_init_db(message: Message):
    # Проверка на админа
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Эта команда доступна только администратору")
        return
        
    try:
        await db.load_data()
        await message.reply("✅ JSON база данных успешно загружена")
    except Exception as e:
        await message.reply(f"❌ Ошибка при загрузке: {str(e)}")

async def handle_my_id(message: Message):
    """Показать ID пользователя"""
    await message.reply(f"🆔 Твой ID: {message.from_user.id}\n🔧 ADMIN_ID: {ADMIN_ID}")

async def handle_delete_avatar(message: Message):
    """Удалить аватарку пользователя"""
    user_id = message.from_user.id
    
    # Удаляем аватарку из базы данных
    await db.update_avatar(user_id, None)
    
    await message.reply("🗑️ Аватарка удалена")

async def handle_change_avatar(message: Message):
    await message.reply("📷 Отправьте изображение или видео для аватарки")

@dp.message(F.photo | F.video)
async def handle_avatar_upload(message: Message):
    # Проверяем, ожидает ли пользователь смены аватара
    # Для упрощения считаем что все фото/видео - это аватарки
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    await db.update_avatar(message.from_user.id, file_id)
    await message.reply("✅ Аватарка обновлена!")

async def handle_close_profile(message: Message):
    await db.toggle_profile(message.from_user.id, True)
    await message.reply("🔒 Профиль закрыт")

async def handle_open_profile(message: Message):
    await db.toggle_profile(message.from_user.id, False)
    await message.reply("🔓 Профиль открыт")

# Админ функции
async def handle_ban_user(message: Message):
    target_id = await get_target_user(message)
    if target_id:
        await db.ban_user(target_id)
        await message.reply(f"✅ Пользователь {target_id} забанен")

async def handle_unban_user(message: Message):
    try:
        user_id = int(message.text.split()[1])
        await db.unban_user(user_id)
        await message.reply(f"✅ Пользователь {user_id} разбанен")
    except (ValueError, IndexError):
        await message.reply("❌ Использование: unbanuser [ID]")

async def handle_game_control(message: Message):
    """Управление играми"""
    settings = await db.get_game_settings()
    
    # Создаем кнопки с текущим статусом
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📊 Трейд {'✅' if settings.get('trade', True) else '🚫'}", 
                    callback_data="game_trade"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"💎 Мины {'✅' if settings.get('mines', True) else '🚫'}", 
                    callback_data="game_mines"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎰 Слоты {'✅' if settings.get('slots', True) else '🚫'}", 
                    callback_data="game_slots"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎡 Вилин {'✅' if settings.get('wheel', True) else '🚫'}", 
                    callback_data="game_wheel"
                )
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить статус", callback_data="game_refresh")
            ]
        ]
    )
    
    status_text = "🎮 УПРАВЛЕНИЕ ИГРАМИ\n\n"
    status_text += "✅ - Игра включена\n"
    status_text += "🚫 - Игра отключена\n\n"
    status_text += "Нажмите на игру чтобы изменить статус"
    
    await message.reply(status_text, reply_markup=keyboard)

# Callback handlers для управления играми
@dp.callback_query(F.data.startswith("game_"))
async def game_control_callback(callback: types.CallbackQuery):
    data_parts = callback.data.split("_")
    
    if data_parts[1] == "refresh":
        # Обновляем статус
        await handle_game_control(callback.message)
        await callback.answer("Статус обновлен")
        return
    
    game_key = data_parts[1]
    game_names = {
        "trade": "Трейд",
        "mines": "Мины",
        "slots": "Слоты", 
        "wheel": "Вилин"
    }
    
    game_name = game_names.get(game_key, game_key)
    settings = await db.get_game_settings()
    current_status = settings.get(game_key, True)
    
    # Переключаем статус
    new_status = not current_status
    await db.toggle_game(game_key, new_status)
    
    # Обновляем меню
    updated_settings = await db.get_game_settings()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📊 Трейд {'✅' if updated_settings.get('trade', True) else '🚫'}", 
                    callback_data="game_trade"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"💎 Мины {'✅' if updated_settings.get('mines', True) else '🚫'}", 
                    callback_data="game_mines"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎰 Слоты {'✅' if updated_settings.get('slots', True) else '🚫'}", 
                    callback_data="game_slots"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎡 Вилин {'✅' if updated_settings.get('wheel', True) else '🚫'}", 
                    callback_data="game_wheel"
                )
            ],
            [
                InlineKeyboardButton(text="� Обновить статус", callback_data="game_refresh")
            ]
        ]
    )
    
    status_text = f"🎮 УПРАВЛЕНИЕ ИГРАМИ\n\n"
    status_text += f"✅ - Игра включена\n"
    status_text += f"🚫 - Игра отключена\n\n"
    status_text += f"Игра '{game_name}': {'✅ Включена' if new_status else '🚫 Отключена'}"
    
    await callback.message.edit_text(status_text, reply_markup=keyboard)
    await callback.answer(f"Игра '{game_name}': {'включена' if new_status else 'отключена'}")

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_game_callback(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    game_key = parts[1]
    action = parts[2]
    
    game_names = {
        "trade": "Трейд",
        "mines": "Мины",
        "slots": "Слоты",
        "wheel": "Вилин"
    }
    
    game_name = game_names.get(game_key, game_key)
    enabled = action == "on"
    
    await db.toggle_game(game_key, enabled)
    
    status_text = "✅ Включена" if enabled else "🚫 Отключена"
    await callback.message.edit_text(
        f"🎮 Игра '{game_name}' {status_text.lower()}"
    )
    await callback.answer()

async def handle_give_admin(message: Message):
    # Проверка на админа
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Эта команда доступна только администратору")
        return
        
    try:
        parts = message.text.split()
        amount = int(parts[1])
        target_id = await get_target_user(message)
        
        if target_id:
            await db.update_balance(target_id, amount)
            await message.reply(f"✅ Выдано {amount} MEM пользователю {target_id}")
        else:
            await message.reply("❌ Пользователь не найден")
    except (ValueError, IndexError):
        await message.reply("❌ Использование: выдать [сумма]")

async def handle_take_admin(message: Message):
    # Проверка на админа
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Эта команда доступна только администратору")
        return
        
    try:
        parts = message.text.split()
        amount = int(parts[1])
        target_id = await get_target_user(message)
        
        if target_id:
            await db.update_balance(target_id, -amount)
            await message.reply(f"✅ Забрано {amount} MEM у пользователя {target_id}")
        else:
            await message.reply("❌ Пользователь не найден")
    except (ValueError, IndexError):
        await message.reply("❌ Использование: забрать [сумма]")

# Callback handlers
@dp.callback_query(F.data.startswith("help_"))
async def help_callback(callback: types.CallbackQuery):
    if callback.data == "help_basic":
        text = """
📋 ОСНОВНЫЕ КОМАНДЫ:

💰 Б / Баланс - показать баланс
🏦 Банк - показать баланс банка
👤 Профиль - информация о профиле
🎒 Инвентарь - ваши предметы
🏆 Топ - топ игроков
💎 Бонус - получить бонус
❓ Помощь - это меню

Переводы:
📤 Дать [сумма] - перевести MEM

Банк:
🏦 Банк снять [сумма] - снять с банка
🏦 Банк пополнить [сумма] - положить в банк

Профиль:
🖼️ Сменить аватарку - изменить фото профиля
🔒 Б закрыть - скрыть баланс в профиле
🔓 Б открыть - показать баланс в профиле
        """
    elif callback.data == "help_games":
        text = """
🎮 ИГРЫ:

💎 Мины [ставка] - игра с поиском алмазов
🎰 Слоты [ставка] - вращение барабанов  
📊 Трейдап [ставка] - ставка на рост графика
📉 Трейдовн [ставка] - ставка на падение графика

Минимальная ставка во всех играх: 100 MEM
        """
    
    await callback.message.edit_text(f"<blockquote>{text}</blockquote>", reply_markup=get_help_keyboard(), parse_mode="HTML")
    await callback.answer()

# Callback handlers для игр
@dp.callback_query(F.data.startswith("mines_"))
async def mines_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "mines_cashout":
        await mines_game.handle_cashout(callback, user_id)
    elif callback.data.startswith("mines_reveal_"):
        try:
            cell_num = int(callback.data.split("_")[2])
            await mines_game.handle_cell_click(callback, user_id, cell_num)
        except (ValueError, IndexError):
            await callback.answer("Ошибка", show_alert=True)

async def handle_close_profile(message: Message):
    """Закрыть профиль (скрыть баланс)"""
    user_id = message.from_user.id
    await db.update_profile_visibility(user_id, False)
    await message.reply("🔒 Профиль закрыт - баланс скрыт")

async def handle_open_profile(message: Message):
    """Открыть профиль (показать баланс)"""
    user_id = message.from_user.id
    await db.update_profile_visibility(user_id, True)
    await message.reply("🔓 Профиль открыт - баланс виден")

async def daily_leaderboard_payout():
    """Ежедневные выплаты лидерборду в 00:00"""
    while True:
        try:
            # Ждем до 00:00
            now = datetime.now()
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            sleep_seconds = (tomorrow - now).total_seconds()
            
            print(f"Следующая выплата лидерборда через {sleep_seconds} секунд")
            await asyncio.sleep(sleep_seconds)
            
            # Получаем топ 5 игроков
            leaderboard = await db.get_leaderboard(5)
            
            if leaderboard:
                payouts = [250000, 150000, 100000, 75000, 50000]  # Призы для 1-5 мест
                
                for i, user in enumerate(leaderboard):
                    if i < len(payouts):
                        prize = payouts[i]
                        await db.update_balance(user['user_id'], prize)
                        
                        # Отправляем уведомление победителю
                        try:
                            await bot.send_message(
                                user['user_id'],
                                f"🏆 ПОЗДРАВЛЯЕМ!\n\n"
                                f"Вы заняли {i+1} место в ежедневном лидерборде!\n"
                                f"💰 Ваш приз: {prize} MEM\n\n"
                                f"Спасибо за игру! 🎮"
                            )
                        except:
                            print(f"Не удалось отправить уведомление пользователю {user['user_id']}")
                
                print(f"Выплачены призы лидерборда: {len(leaderboard)} игроков")
            
            # Сбрасываем ежедневные выигрыши
            await db.reset_daily_winnings()
            print("Ежедневные выигрыши сброшены")
            
        except Exception as e:
            print(f"Ошибка в ежедневных выплатах: {e}")
            await asyncio.sleep(60)  # Пауза при ошибке

async def startup():
    """Запуск бота"""
    await db.load_data()
    print("Бот запущен и данные загружены")
    
    # Запускаем фоновую задачу для ежедневных выплат
    asyncio.create_task(daily_leaderboard_payout())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(startup())
