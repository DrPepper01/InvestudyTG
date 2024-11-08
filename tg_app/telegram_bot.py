import asyncio
import logging
import os
import django
from uuid import uuid4
from io import BytesIO
import base64
from html import escape
from asgiref.sync import sync_to_async
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjectTG.settings')
django.setup()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation stages
ASK_PAGE, ASK_DESCRIPTION, ASK_SCREENSHOT, ASK_ADDITIONAL_INFO = range(4)

# Handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Greets the user and prompts them to select the app page where the issue occurred."""
    await update.message.reply_text(FAQ_TEXT)

    keyboard = [
        [KeyboardButton("Бюджет"), KeyboardButton("Профиль")],
        [KeyboardButton("Лента"), KeyboardButton("Инвестиции")],
        [KeyboardButton("Долги"), KeyboardButton("Другое")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Здравствуйте! Выберите, на какой странице приложения возникла ошибка.", reply_markup=reply_markup)
    return ASK_PAGE


# Handler for selecting the page
async def ask_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the selected page and prompts for a problem description."""
    selected_page = update.message.text
    context.user_data['selected_page'] = selected_page
    await update.message.reply_text(f"Вы выбрали страницу: {selected_page}. Пожалуйста, опишите вашу проблему подробно.")
    return ASK_DESCRIPTION

# Handler for problem description
async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the problem description and requests a screenshot, with a minimum text length check."""
    user = update.message.from_user
    user_response = update.message.text

    # Check for minimum response length
    if len(user_response) < 5:
        await update.message.reply_text(
            "Кажется, ваш ответ слишком краткий. Пожалуйста, опишите проблему подробнее."
        )
        return ASK_DESCRIPTION

    # Wraps database access in sync_to_async
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

    keyboard = [[KeyboardButton("Нет")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Спасибо! Пожалуйста, отправьте скриншот или фото, иллюстрирующее проблему. "
        "Если у вас нет скриншота, нажмите 'Нет' для пропуска.",
        reply_markup=reply_markup
    )
    return ASK_SCREENSHOT

# Handler for receiving the screenshot
async def ask_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the screenshot and requests additional information."""
    keyboard = [[KeyboardButton("Нет")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    if update.message.photo:
        # If the user sent a photo, save it
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        encoded_photo = base64.b64encode(photo_bytes).decode('utf-8')
        context.user_data['screenshot'] = {
            'file_name': f'{update.message.from_user.id}_{uuid4()}.jpg',
            'file_data': encoded_photo,
        }
        logger.info("Скриншот получен от пользователя %s", update.message.from_user.id)
    elif update.message.text.lower() == 'нет':
        # If the user sent "нет", proceed to the next step
        context.user_data['screenshot'] = None
        logger.info("Скриншот не предоставлен.")
    else:
        # If the user sent something else, request input again
        await update.message.reply_text(
            "Спасибо! Пожалуйста, отправьте скриншот или фото, иллюстрирующее проблему. "
            "Если у вас нет скриншота, нажмите 'Нет' для пропуска.",
            reply_markup=reply_markup
        )
        return ASK_SCREENSHOT  # Stay on the screenshot stage

    # Proceed to the next step after receiving the image or a correct response "нет"
    await update.message.reply_text(
        "Спасибо! Укажите, пожалуйста, модель вашего устройства, версию ОС и приложения.",
        reply_markup = ReplyKeyboardRemove()
    )
    return ASK_ADDITIONAL_INFO

# Handler for additional information
async def ask_additional_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves additional information and confirms the ticket creation."""
    user_data = context.user_data
    user_profile = user_data['user_profile']
    additional_info = update.message.text
    description = user_data['description']

    # Creates a ticket, wrapped in sync_to_async
    ticket = await sync_to_async(Ticket.objects.create, thread_sensitive=True)(
        user=user_profile,  # Use only user_profile
        description=description,
        additional_info=additional_info
    )
    user_data['ticket'] = ticket

    # Saves the screenshot (if present), also wrapped in sync_to_async
    if user_data.get('screenshot'):
        await sync_to_async(Attachment.objects.create, thread_sensitive=True)(
            ticket=ticket,
            file_name=user_data['screenshot']['file_name'],
            file_data=user_data['screenshot']['file_data']
        )

    # Generates a message for the user
    confirmation_message = (
        f"Спасибо! Ваша заявка зарегистрирована под номером #{ticket.ticket_id}.\n"
        "Наша команда поддержки свяжется с вами в ближайшее время."
    )

    await update.message.reply_text(confirmation_message)

    # Sends information to the support team
    await notify_support_team(context, update, ticket)

    # Clears user data
    context.user_data.clear()

    return ConversationHandler.END

# Function for notifying the support team
async def notify_support_team(context: ContextTypes.DEFAULT_TYPE, update: Update, ticket: Ticket):
    """Sends issue information to the support chat."""
    support_chat_id = settings.SUPPORT_CHAT_ID
    selected_page = context.user_data.get('selected_page', 'Неизвестно')
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
    """Cancels the dialog."""
    await update.message.reply_text(
        "Вы отменили обращение. Если у вас возникнут вопросы, напишите мне снова."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends bot description when using the /help command."""
    await update.message.reply_text(HELP_TEXT)

FAQ_TEXT = """

Убедитесь что у вас установлена последняя версия приложения в App Store/Google play market. 

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

Бот тех.поддержки для пользователей  Investudy App
С помощью него вы можете:
    1. Сообщить о возникшей проблеме.
    2. Приложить скриншоты или фото для лучшего описания ситуации.
    3. Получить ответ от нашей команды поддержки.
"""


# Function to set bot commands
async def post_init(application: Application):
    await application.bot.set_my_commands([
        ('start', 'Начать обращение'),
        ('help', 'Описание возможностей бота')
    ])

def main():
    """Main application startup."""
    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Defining conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_PAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_page)],
            ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
            ASK_SCREENSHOT: [MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), ask_screenshot)],
            ASK_ADDITIONAL_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_additional_info)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Adding command handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))

    # Launch the bot in polling mode
    application.run_polling()

if __name__ == '__main__':
    main()