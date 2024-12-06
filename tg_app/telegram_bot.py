# bot.py
import asyncio
import logging
import os
import django
from uuid import uuid4
from io import BytesIO
import base64
from html import escape
from asgiref.sync import sync_to_async
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler, Application,
)
from telegram.error import ChatMigrated
from django.conf import settings
from tg_app.models import UserProfile, Ticket, Attachment

# Инициализация Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjectTG.settings')
django.setup()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для диалогов
ASK_PAGE, ASK_DESCRIPTION, ASK_SCREENSHOT, ASK_ADDITIONAL_INFO = range(4)
# Новые состояния для диалога предложений
SUGGESTION_PAGE, SUGGESTION_SECTION, SUGGESTION_TEXT = range(10, 13)

# Текст справки и FAQ
FAQ_TEXT = """

Убедитесь, что у вас установлена последняя версия приложения в App Store/Google Play Market.

1. Как завести бюджет в приложении?
Ответ: Для добавления бюджета, нажмите на раздел “Бюджеты” и выберите “Создать новый бюджет”. Заполните название, категории расходов и планируемую сумму. Нажмите “Сохранить” для сохранения.

2. Как отслеживать долги в приложении?
Ответ: В разделе “Долги” нажмите на “Добавить новый долг”. Укажите сумму долга, дату выплаты и контакт для связи. При выплате обновляйте статус долга, чтобы видеть прогресс.

3. Как работает кредитный калькулятор?
Ответ: Выберите раздел “Кредитный калькулятор”. Введите сумму кредита, процентную ставку и срок в месяцах. Кликните на “Рассчитать”, чтобы получить ежемесячные платежи и итоговую сумму.

4. Как добавить инвестиции в приложение?
Ответ: Перейдите в раздел “Инвестиции” и нажмите “Добавить инвестицию”. Укажите тип инвестиции, сумму и срок вложения. Приложение автоматически рассчитает прогнозируемый доход.

5. Можно ли настроить уведомления о финансовых событиях?
Ответ: Да, в разделе “Настройки” выберите “Уведомления” и настройте оповещения о запланированных выплатах, изменениях бюджета и инвестициях.
"""

HELP_TEXT = """

Бот техподдержки для пользователей Investudy App.
С помощью него вы можете:
1. Сообщить о возникшей проблеме через команду /start.
2. Предложить улучшения приложения через команду /suggestions.
3. Приложить скриншоты или фото для лучшего описания ситуации.
4. Получить ответ от нашей команды поддержки.
"""

async def log_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    print(f"Chat ID: {chat_id}")
    await update.message.reply_text(f"Ваш Chat ID: {chat_id}")

# Функция для тестирования
async def send_test_message(chat_id: str, message: str):
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id='550727902', text=message)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Приветствие пользователя и запрос страницы с проблемой."""
    await update.message.reply_text(FAQ_TEXT)

    keyboard = [
        [KeyboardButton("Бюджет"), KeyboardButton("Профиль")],
        [KeyboardButton("Лента"), KeyboardButton("Инвестиции")],
        [KeyboardButton("Долги"), KeyboardButton("Другое")],
        [KeyboardButton("Отмена")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Здравствуйте! Выберите, на какой странице приложения возникла ошибка.",
        reply_markup=reply_markup
    )
    return ASK_PAGE

# Обработчики для диалога обращения
async def ask_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет выбранную страницу и запрашивает описание проблемы."""
    if update.message.text == "Отмена":
        return await cancel(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    selected_page = update.message.text
    context.user_data['selected_page'] = selected_page
    await update.message.reply_text(
        f"Вы выбрали страницу: {selected_page}. Пожалуйста, опишите вашу проблему подробно.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_DESCRIPTION

async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет описание проблемы и запрашивает скриншот."""
    if update.message.text == "Отмена":
        return await cancel(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    user = update.message.from_user
    user_response = update.message.text

    # Проверка на минимальную длину ответа
    if len(user_response) < 5:
        await update.message.reply_text(
            "Кажется, ваш ответ слишком краткий. Пожалуйста, опишите проблему подробнее."
        )
        return ASK_DESCRIPTION

    # Получение или создание профиля пользователя
    user_profile, created = await sync_to_async(UserProfile.objects.get_or_create, thread_sensitive=True)(
        telegram_id=user.id,
        defaults={
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    )

    context.user_data['user_profile'] = user_profile
    context.user_data['description'] = user_response
    logger.info("Проблема от %s: %s", user.first_name, user_response)

    keyboard = [[KeyboardButton("Нет"), KeyboardButton("Отмена")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Спасибо! Пожалуйста, отправьте скриншот или фото, иллюстрирующее проблему. "
        "Если у вас нет скриншота, нажмите 'Нет' для пропуска.",
        reply_markup=reply_markup
    )
    return ASK_SCREENSHOT


async def ask_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет скриншот и запрашивает дополнительную информацию."""
    user_input = update.message.text if update.message.text else ""

    if user_input == "Отмена":
        return await cancel(update, context)

    if user_input.startswith('/'):
        return await handle_command_during_conversation(update, context)

    keyboard = [[KeyboardButton("Отмена")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    if update.message.photo:
        # Сохранение фото
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        encoded_photo = base64.b64encode(photo_bytes).decode('utf-8')
        context.user_data['screenshot'] = {
            'file_name': f'{update.message.from_user.id}_{uuid4()}.jpg',
            'file_data': encoded_photo,
        }
        logger.info("Скриншот получен от пользователя %s", update.message.from_user.id)

        await update.message.reply_text(
            "Спасибо! Укажите, пожалуйста, модель вашего устройства, версию ОС и приложения.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_ADDITIONAL_INFO

    elif user_input.lower() == 'нет':
        context.user_data['screenshot'] = None
        logger.info("Скриншот не предоставлен.")

        await update.message.reply_text(
            "Спасибо! Укажите, пожалуйста, модель вашего устройства, версию ОС и приложения.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_ADDITIONAL_INFO

    else:
        await update.message.reply_text(
            "Пожалуйста, отправьте скриншот или фото, иллюстрирующее проблему. "
            "Если у вас нет скриншота, напишите 'Нет' для пропуска.",
            reply_markup=reply_markup
        )
        return ASK_SCREENSHOT

async def handle_unexpected_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает фото, отправленные вне контекста диалога."""
    await update.message.reply_text(
        "Если вы хотите отправить фото с ошибкой, нажмите /start, выберите страницу, на которой возникает ошибка, и следуйте дальнейшим инструкциям."
    )

async def ask_additional_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет дополнительную информацию и подтверждает создание тикета."""
    if update.message.text == "Отмена":
        return await cancel(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    user_data = context.user_data
    user_profile = user_data['user_profile']
    additional_info = update.message.text
    description = user_data['description']

    # Создание тикета
    ticket = await sync_to_async(Ticket.objects.create, thread_sensitive=True)(
        user=user_profile,
        description=description,
        additional_info=additional_info,
        page=context.user_data.get('selected_page', ''),
    )
    user_data['ticket'] = ticket

    # Сохранение скриншота
    if user_data.get('screenshot'):
        await sync_to_async(Attachment.objects.create, thread_sensitive=True)(
            ticket=ticket,
            file_name=user_data['screenshot']['file_name'],
            file_data=user_data['screenshot']['file_data']
        )

    confirmation_message = (
        f"Спасибо! Ваша заявка зарегистрирована под номером #{ticket.ticket_id}.\n"
        "Наша команда поддержки свяжется с вами в ближайшее время."
    )

    await update.message.reply_text(confirmation_message)

    # Отправка информации в чат поддержки
    await notify_support_team(context, update, ticket)

    # Очистка данных пользователя
    context.user_data.clear()

    return ConversationHandler.END

async def notify_support_team(context: ContextTypes.DEFAULT_TYPE, update: Update, ticket: Ticket):
    """Отправляет информацию о проблеме в чат поддержки."""
    support_chat_id = settings.SUPPORT_CHAT_ID
    selected_page = ticket.page or 'Неизвестно'
    message = (
        f"Новая заявка #{ticket.ticket_id}\n"
        f"От пользователя: @{escape(update.message.from_user.username)} ({escape(update.message.from_user.first_name)})\n\n"
        f"Страница: {escape(selected_page)}\n"
        f"<b>Описание проблемы:</b>\n{escape(ticket.description)}\n\n"
        f"<b>Дополнительная информация:</b>\n{escape(ticket.additional_info)}"
    )

    has_attachments = await sync_to_async(ticket.attachments.exists, thread_sensitive=True)()
    try:
        if has_attachments:
            attachment = await sync_to_async(ticket.attachments.first, thread_sensitive=True)()
            photo_bytes = base64.b64decode(attachment.file_data)
            photo_file = BytesIO(photo_bytes)
            photo_file.name = attachment.file_name

            await context.bot.send_photo(
                chat_id=support_chat_id,
                photo=photo_file,
                caption=message,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_message(
                chat_id=support_chat_id,
                text=message,
                parse_mode='HTML'
            )
    except ChatMigrated as e:
        new_chat_id = e.new_chat_id
        settings.SUPPORT_CHAT_ID = new_chat_id
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в чат поддержки: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    await update.message.reply_text(
        "Вы отменили процесс. Если у вас возникнут вопросы, напишите мне снова.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Обработчики для диалога предложений
async def suggestions_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог предложений и запрашивает страницу."""
    keyboard = [
        [KeyboardButton("Бюджет"), KeyboardButton("Профиль")],
        [KeyboardButton("Лента"), KeyboardButton("Инвестиции")],
        [KeyboardButton("Долги"), KeyboardButton("Другое")],
        [KeyboardButton("Отмена")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Выберите страницу, на которой вы бы хотели видеть улучшение:",
        reply_markup=reply_markup
    )
    return SUGGESTION_PAGE

async def suggestion_page_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет выбранную страницу и предлагает выбрать вкладку или ввести текст."""
    if update.message.text == "Отмена":
        return await cancel_suggestion(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    selected_page = update.message.text
    context.user_data['selected_page'] = selected_page

    if selected_page == "Бюджет":
        keyboard = [
            [KeyboardButton("Расходы"), KeyboardButton("Доходы")],
            [KeyboardButton("Счета"), KeyboardButton("План")],
            [KeyboardButton("Отмена")]
        ]
    elif selected_page == "Долги":
        keyboard = [
            [KeyboardButton("Все"), KeyboardButton("Кредиты")],
            [KeyboardButton("Рассрочки"), KeyboardButton("Мои долги")],
            [KeyboardButton("Мои должники"), KeyboardButton("Отмена")]
        ]
    elif selected_page == "Инвестиции":
        keyboard = [
            [KeyboardButton("Все"), KeyboardButton("Депозит")],
            [KeyboardButton("Фондовый рынок"), KeyboardButton("Краудфандинг")],
            [KeyboardButton("Долевой бизнес"), KeyboardButton("Криптовалюта")],
            [KeyboardButton("Отмена")]
        ]
    elif selected_page == "Лента":
        keyboard = [
            [KeyboardButton("Новости"), KeyboardButton("Kase")],
            [KeyboardButton("Медиа"), KeyboardButton("Авторы")],
            [KeyboardButton("Отмена")]
        ]
    elif selected_page == "Профиль":
        await update.message.reply_text(
            "Пожалуйста, опишите ваше предложение:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
        )
        return SUGGESTION_TEXT
    else:
        # Если выбрано "Другое" или некорректный ввод
        await update.message.reply_text(
            "Пожалуйста, опишите ваше предложение:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
        )
        return SUGGESTION_TEXT

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"Выберите вкладку на странице '{selected_page}', в которой вы бы хотели что-то улучшить:",
        reply_markup=reply_markup
    )
    return SUGGESTION_SECTION

async def suggestion_section_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет выбранную вкладку и запрашивает текст предложения."""
    if update.message.text == "Отмена":
        return await cancel_suggestion(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    selected_section = update.message.text
    context.user_data['selected_section'] = selected_section

    await update.message.reply_text(
        "Пожалуйста, опишите ваше предложение:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
    )
    return SUGGESTION_TEXT

async def suggestion_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет текст предложения и отправляет его в чат поддержки вместе с Excel-файлом."""
    if update.message.text == "Отмена":
        return await cancel_suggestion(update, context)

    if update.message.text.startswith('/'):
        return await handle_command_during_conversation(update, context)

    suggestion_text = update.message.text
    user = update.message.from_user
    context.user_data['suggestion_text'] = suggestion_text

    # Получение или создание профиля пользователя
    user_profile, created = await sync_to_async(UserProfile.objects.get_or_create, thread_sensitive=True)(
        telegram_id=user.id,
        defaults={
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    )

    # Создание записи предложения в базе данных
    suggestion = await sync_to_async(Ticket.objects.create, thread_sensitive=True)(
        user=user_profile,
        description=suggestion_text,
        page=context.user_data.get('selected_page', ''),
        section=context.user_data.get('selected_section', ''),
        is_suggestion=True  # Флаг для различения предложений
    )

    # Генерация Excel-файла
    excel_file = await generate_excel_file(suggestion)

    # Отправка информации в чат поддержки
    await notify_support_team_suggestion(context, update, suggestion, excel_file)

    # Удаление временного файла
    excel_file.close()
    os.remove(excel_file.name)

    await update.message.reply_text(
        "Спасибо за ваше предложение! Мы ценим ваш вклад в развитие нашего приложения.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Очистка данных пользователя
    context.user_data.clear()

    return ConversationHandler.END

async def notify_support_team_suggestion(context: ContextTypes.DEFAULT_TYPE, update: Update, suggestion: Ticket, excel_file):
    """Отправляет информацию о предложении в чат поддержки вместе с Excel-файлом."""
    support_chat_id = settings.SUPPORT_CHAT_ID
    message = (
        f"Новое предложение #{suggestion.ticket_id}\n"
        f"От пользователя: @{escape(update.message.from_user.username)} ({escape(update.message.from_user.first_name)})\n\n"
        f"Страница: {escape(suggestion.page)}\n"
        f"Вкладка: {escape(suggestion.section)}\n"
        f"Дата отправки предложения: {suggestion.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"<b>Текст предложения:</b>\n{escape(suggestion.description)}"
    )

    try:
        await context.bot.send_document(
            chat_id=support_chat_id,
            document=excel_file,
            caption=message,
            parse_mode='HTML'
        )
    except ChatMigrated as e:
        new_chat_id = e.new_chat_id
        settings.SUPPORT_CHAT_ID = new_chat_id
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в чат поддержки: {e}")

async def cancel_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога предложений."""
    await update.message.reply_text(
        "Вы отменили отправку предложения. Если захотите поделиться идеями, напишите /suggestions.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Вспомогательные функции
async def get_user_profile(user):
    user_profile, created = await sync_to_async(UserProfile.objects.get_or_create, thread_sensitive=True)(
        telegram_id=user.id,
        defaults={
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
    )
    return user_profile

import pandas as pd
from tempfile import NamedTemporaryFile

async def generate_excel_file(suggestion):
    data = {
        'Пользователь': [f'{suggestion.user.first_name} @{suggestion.user.username}'],
        'Страница': [suggestion.page],
        'Вкладка': [suggestion.section],
        'Дата отправки предложения': [suggestion.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        'Текст предложения': [suggestion.description],
        'Номер предложения в БД': [suggestion.ticket_id],
    }
    df = pd.DataFrame(data)
    temp_file = NamedTemporaryFile(delete=False, suffix='.xlsx')
    df.to_excel(temp_file.name, index=False)
    temp_file.seek(0)
    return temp_file

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет описание возможностей бота при использовании команды /help."""
    await update.message.reply_text(HELP_TEXT)

async def handle_command_during_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает команды во время активного диалога."""
    command = update.message.text.strip().lower()
    if command == '/start':
        await cancel(update, context)
        return await start(update, context)
    elif command == '/suggestions':
        await cancel(update, context)
        return await suggestions_start(update, context)
    elif command == '/help':
        await update.message.reply_text(HELP_TEXT)
        return ConversationHandler.END  # Завершаем текущий диалог
    else:
        await update.message.reply_text(
            "Извините, я не понимаю эту команду. Пожалуйста, продолжайте или нажмите 'Отмена' для завершения.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

# Функция для установки команд бота
async def post_init(application: Application):
    await application.bot.set_my_commands([
        ('start', 'Начать обращение'),
        ('suggestions', 'Предложить улучшения'),
        ('help', 'Описание возможностей бота')
    ])

def main():
    """Основная функция запуска приложения."""
    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Обработчики диалогов
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_PAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_page),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
            ASK_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
            ASK_SCREENSHOT: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), ask_screenshot),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
            ASK_ADDITIONAL_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_additional_info),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start),
            CommandHandler('suggestions', suggestions_start),
            MessageHandler(filters.Regex('^Отмена$'), cancel),
            MessageHandler(filters.COMMAND, handle_command_during_conversation),
        ],
    )

    suggestions_handler = ConversationHandler(
        entry_points=[CommandHandler('suggestions', suggestions_start)],
        states={
            SUGGESTION_PAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, suggestion_page_selected),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
            SUGGESTION_SECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, suggestion_section_selected),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
            SUGGESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, suggestion_text_received),
                MessageHandler(filters.COMMAND, handle_command_during_conversation),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_suggestion),
            CommandHandler('start', start),
            CommandHandler('suggestions', suggestions_start),
            MessageHandler(filters.Regex('^Отмена$'), cancel_suggestion),
            MessageHandler(filters.COMMAND, handle_command_during_conversation),
        ],
    )

    # Добавление обработчиков
    application.add_handler(MessageHandler(filters.PHOTO, handle_unexpected_photo))  # Новый обработчик
    application.add_handler(conv_handler)
    application.add_handler(suggestions_handler)
    application.add_handler(CommandHandler("help", help_command))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
