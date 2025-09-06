from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import os
import json
import logging
from datetime import datetime

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

# Админские ID (добавьте свои ID сюда)
ADMIN_IDS = [1249391970]  # Rick Morrison (@rhhiko)

CATEGORIES = {
    "shit": "Про говно",
    "covers": "Каверы",
    "quotes": "Цитаты"
}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
STATS_FILE = 'statistics.json'
MESSAGES_LOG = 'messages_log.json'


def is_admin(user_id):
    """Проверяет, является ли пользователь админом"""
    return user_id in ADMIN_IDS


def log_message(update: Update, action: str, details: str = ""):
    """Логирует сообщения и действия пользователей"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'chat_id': chat.id,
            'chat_type': chat.type,
            'action': action,
            'details': details
        }
        
        # Записываем в файл
        try:
            with open(MESSAGES_LOG, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []
        
        logs.append(log_entry)
        
        with open(MESSAGES_LOG, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        # Логируем в консоль
        logger.info(f"User {user.first_name} ({user.id}): {action} - {details}")
        
    except Exception as e:
        logger.error(f"Ошибка логирования: {e}")


def update_statistics(user_id: int, category: str, audio_file: str):
    """Обновляет статистику использования"""
    try:
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            stats = {}
        
        if user_id not in stats:
            stats[user_id] = {
                'total_plays': 0,
                'categories': {},
                'last_activity': None
            }
        
        stats[user_id]['total_plays'] += 1
        stats[user_id]['last_activity'] = datetime.now().isoformat()
        
        if category not in stats[user_id]['categories']:
            stats[user_id]['categories'][category] = 0
        stats[user_id]['categories'][category] += 1
        
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"Ошибка обновления статистики: {e}")


def start(update: Update, context: CallbackContext):
    log_message(update, "start_command", "Пользователь запустил бота")
    
    keyboard = [
        [InlineKeyboardButton(name, callback_data=key)]
        for key, name in CATEGORIES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = update.message.reply_text("🎤 Выбери категорию:", reply_markup=reply_markup)
    context.user_data['last_messages'] = [message.message_id]


def delete_old_messages(context: CallbackContext, chat_id: int):
    if 'last_messages' in context.user_data:
        for msg_id in context.user_data['last_messages']:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
        context.user_data['last_messages'] = []


def category_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    category = query.data

    delete_old_messages(context, chat_id)
    if 'last_messages' not in context.user_data:
        context.user_data['last_messages'] = []
    context.user_data['last_messages'].append(query.message.message_id)

    folder_path = f"media/{category}"
    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.ogg')] if os.path.exists(folder_path) else []

    if not files:
        msg = query.message.reply_text("Нет аудиофайлов в этой категории.")
        context.user_data['last_messages'].append(msg.message_id)
        return

    keyboard = []
    row = []
    for i, file in enumerate(files):
        title = os.path.splitext(file)[0]
        callback_data = f"{category}__{file}"
        row.append(InlineKeyboardButton(title, callback_data=callback_data))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("На зад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    photo_path = f"media/images/{category}.jpg"
    if os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            msg = query.message.reply_photo(photo=photo, caption=f"Категория: {CATEGORIES[category]}", reply_markup=reply_markup)
    else:
        msg = query.message.reply_text(f"Категория: {CATEGORIES[category]}", reply_markup=reply_markup)

    context.user_data['last_messages'].append(msg.message_id)


def audio_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id

    delete_old_messages(context, chat_id)
    if 'last_messages' not in context.user_data:
        context.user_data['last_messages'] = []
    context.user_data['last_messages'].append(query.message.message_id)

    try:
        category, filename = query.data.split("__")
    except ValueError:
        msg = query.message.reply_text("Ошибка разбора данных.")
        context.user_data['last_messages'].append(msg.message_id)
        return

    audio_path = os.path.join("media", category, filename)
    audio_title = os.path.splitext(filename)[0]
    image_path = os.path.join("media", "images", category, f"{audio_title}.jpg")

    buttons = [
        [InlineKeyboardButton("Меню", callback_data="back_to_menu"),
         InlineKeyboardButton("На зад", callback_data=category)]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if os.path.exists(audio_path):
        # Логируем прослушивание
        log_message(update, "audio_play", f"{category}/{filename}")
        update_statistics(query.from_user.id, category, filename)
        
        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                photo_msg = query.message.reply_photo(photo=photo)
                context.user_data['last_messages'].append(photo_msg.message_id)
        with open(audio_path, 'rb') as audio:
            msg = query.message.reply_audio(audio=audio, caption=audio_title, reply_markup=reply_markup)
            context.user_data['last_messages'].append(msg.message_id)
    else:
        log_message(update, "audio_error", f"Файл не найден: {audio_path}")
        msg = query.message.reply_text("🎧 Аудиофайл не найден!")
        context.user_data['last_messages'].append(msg.message_id)


def back_to_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id

    delete_old_messages(context, chat_id)
    if 'last_messages' not in context.user_data:
        context.user_data['last_messages'] = []
    context.user_data['last_messages'].append(query.message.message_id)

    keyboard = [
        [InlineKeyboardButton(name, callback_data=key)]
        for key, name in CATEGORIES.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = query.message.reply_text("🎤 Выбери категорию:", reply_markup=reply_markup)
    context.user_data['last_messages'].append(msg.message_id)


def admin_command(update: Update, context: CallbackContext):
    """Админская панель"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    log_message(update, "admin_panel", "Открыта админская панель")
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Логи сообщений", callback_data="admin_logs")],
        [InlineKeyboardButton("📤 Отправить сообщение", callback_data="admin_send")],
        [InlineKeyboardButton("🔄 Перезагрузить бота", callback_data="admin_restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text("🔧 Админская панель:", reply_markup=reply_markup)


def stats_command(update: Update, context: CallbackContext):
    """Показывает статистику"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        update.message.reply_text("📊 Статистика пуста")
        return
    
    total_users = len(stats)
    total_plays = sum(user_data['total_plays'] for user_data in stats.values())
    
    # Топ категорий
    category_stats = {}
    for user_data in stats.values():
        for category, count in user_data['categories'].items():
            category_stats[category] = category_stats.get(category, 0) + count
    
    top_categories = sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:3]
    
    message = f"📊 **Статистика бота:**\n\n"
    message += f"👥 Всего пользователей: {total_users}\n"
    message += f"🎵 Всего прослушиваний: {total_plays}\n\n"
    message += f"🏆 **Топ категорий:**\n"
    
    for category, count in top_categories:
        category_name = CATEGORIES.get(category, category)
        message += f"• {category_name}: {count}\n"
    
    update.message.reply_text(message, parse_mode='Markdown')


def send_message_command(update: Update, context: CallbackContext):
    """Команда для отправки сообщений"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    if not context.args:
        update.message.reply_text("❌ Использование: /send <chat_id> <сообщение>")
        return
    
    try:
        target_chat_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        if not message_text:
            update.message.reply_text("❌ Сообщение не может быть пустым!")
            return
        
        # Отправляем сообщение
        context.bot.send_message(chat_id=target_chat_id, text=message_text)
        
        log_message(update, "admin_send", f"Отправлено в {target_chat_id}: {message_text}")
        update.message.reply_text(f"✅ Сообщение отправлено в чат {target_chat_id}")
        
    except ValueError:
        update.message.reply_text("❌ Неверный формат chat_id!")
    except Exception as e:
        log_message(update, "admin_send_error", str(e))
        update.message.reply_text(f"❌ Ошибка отправки: {e}")


def admin_callback_handler(update: Update, context: CallbackContext):
    """Обработчик админских callback'ов"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        query.answer("❌ У вас нет прав администратора!")
        return
    
    query.answer()
    
    if query.data == "admin_stats":
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            query.edit_message_text("📊 Статистика пуста")
            return
        
        total_users = len(stats)
        total_plays = sum(user_data['total_plays'] for user_data in stats.values())
        
        message = f"📊 **Статистика бота:**\n\n"
        message += f"👥 Всего пользователей: {total_users}\n"
        message += f"🎵 Всего прослушиваний: {total_plays}\n\n"
        message += f"📈 **Активность:**\n"
        
        # Последние 5 пользователей
        recent_users = sorted(stats.items(), 
                            key=lambda x: x[1].get('last_activity', ''), 
                            reverse=True)[:5]
        
        for user_id, user_data in recent_users:
            last_activity = user_data.get('last_activity', 'Неизвестно')
            if last_activity != 'Неизвестно':
                try:
                    dt = datetime.fromisoformat(last_activity)
                    last_activity = dt.strftime('%d.%m.%Y %H:%M')
                except:
                    pass
            message += f"• ID {user_id}: {user_data['total_plays']} прослушиваний (последняя активность: {last_activity})\n"
        
        query.edit_message_text(message, parse_mode='Markdown')
        
    elif query.data == "admin_logs":
        try:
            with open(MESSAGES_LOG, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            query.edit_message_text("📝 Логи пусты")
            return
        
        # Последние 10 записей
        recent_logs = logs[-10:] if len(logs) > 10 else logs
        
        message = "📝 **Последние 10 действий:**\n\n"
        for log in recent_logs:
            timestamp = log.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime('%d.%m %H:%M')
                except:
                    pass
            
            user_name = log.get('first_name', 'Unknown')
            action = log.get('action', 'Unknown')
            details = log.get('details', '')
            
            message += f"• {timestamp} - {user_name}: {action}"
            if details:
                message += f" ({details})"
            message += "\n"
        
        query.edit_message_text(message, parse_mode='Markdown')
        
    elif query.data == "admin_send":
        query.edit_message_text("📤 Для отправки сообщения используйте команду:\n/send <chat_id> <сообщение>")
        
    elif query.data == "admin_restart":
        query.edit_message_text("🔄 Перезагрузка бота...")
        log_message(update, "admin_restart", "Админ перезагрузил бота")
        # Здесь можно добавить логику перезагрузки


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Устанавливаем кнопку меню только с командой /start
    try:
        updater.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        # Устанавливаем только команду /start в меню
        updater.bot.set_my_commands([('start', 'Запустить бота')])
        print("✅ Кнопка меню установлена с командой /start!")
    except Exception as e:
        print(f"⚠️ Не удалось установить кнопку меню: {e}")

    # Основные команды
    dp.add_handler(CommandHandler('start', start))
    
    # Админские команды (скрытые, не показываются в меню)
    dp.add_handler(CommandHandler('admin', admin_command))
    dp.add_handler(CommandHandler('stats', stats_command))
    dp.add_handler(CommandHandler('send', send_message_command))
    
    # Обработчики callback'ов
    dp.add_handler(CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'))
    dp.add_handler(CallbackQueryHandler(category_handler, pattern='^(' + '|'.join(CATEGORIES.keys()) + ')$'))
    dp.add_handler(CallbackQueryHandler(audio_handler, pattern='^(' + '|'.join(CATEGORIES.keys()) + ')__.*$'))
    dp.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^admin_.*$'))

    logger.info("🤖 Бот запущен с новыми функциями!")
    print("🤖 Бот запущен с новыми функциями!")
    print("📊 Доступные команды:")
    print("  /start - запуск бота")
    print("  /admin - админская панель")
    print("  /stats - статистика")
    print("  /send <chat_id> <сообщение> - отправить сообщение")
    print("🔘 Кнопка меню активирована!")
    
    # Для Heroku - получаем порт из переменной окружения
    port = int(os.environ.get('PORT', 5000))
    
    # Запускаем бота
    updater.start_polling()
    print(f"🚀 Бот запущен на порту {port}")
    updater.idle()


if __name__ == '__main__':
    main()
