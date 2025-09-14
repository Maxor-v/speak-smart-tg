import os
import asyncio
from tempfile import NamedTemporaryFile
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from database import db
from evaluation import check_answer, recognize_speech_from_file, handle_user_query, convert_ogg_to_wav
from logger import log_message, log_error, log_practice_session, logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_OPERATOR_ID
from models import Phrase

# Получение токена из переменных окружения
BOT_TOKEN = TELEGRAM_BOT_TOKEN
OPERATOR_ID = TELEGRAM_OPERATOR_ID

if not BOT_TOKEN:
    raise ValueError("Не задан TELEGRAM_BOT_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# Состояния FSM
class PracticeState(StatesGroup):
    waiting_for_response = State()
    in_practice = State()


class SupportState(StatesGroup):
    waiting_question = State()


# Клавиатуры
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎯 Практика"), KeyboardButton(text="❓ Поддержка")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

practice_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔁 Новая фраза"), KeyboardButton(text="⏹️ Завершить")],
    ],
    resize_keyboard=True
)

support_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❓ Частые вопросы"), KeyboardButton(text="👨‍💻 Оператор")],
        [KeyboardButton(text="🔙 Назад")],
    ],
    resize_keyboard=True
)

# Мидлварь для логирования пользовательской активности
@dp.update.middleware()
async def user_activity_middleware(handler, event, data):
    try:
        if event.message:
            user = event.message.from_user
            await db.add_user(user.id, user.username, user.first_name, user.last_name)
            await db.update_user_activity(user.id)
        return await handler(event, data)
    except Exception as e:
        await log_error(db, "MiddlewareError", f"Error in user activity middleware: {e}")
        return await handler(event, data)


# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start - приветственное сообщение"""
    try:
        await message.answer(
            "👋 Добро пожаловать в языкового бота!\n\n"
            "Вы можете:\n"
            "• Практиковать иностранную речь 🎯\n"
            "• Получить помощь по использованию ❓\n\n"
            "Выберите действие:",
            reply_markup=main_keyboard
        )
        await log_message(db, message.from_user.id, None, "outgoing", "Приветственное сообщение")
    except Exception as e:
        await log_error(db, "StartError", f"Error in start command: {e}", user_id=message.from_user.id)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help - справка по командам"""
    try:
        await message.answer(
            "📖 <b>Доступные команды:</b>\n\n"
            "/start - начать работу\n"
            "/practice - начать практику\n"
            "/support - обращение в поддержку\n"
            "/stats - показать статистику\n\n"
            "Или используйте кнопки меню ↓",
            reply_markup=main_keyboard
        )
        await log_message(db, message.from_user.id, None, "outgoing", "Сообщение помощи")
    except Exception as e:
        await log_error(db, "HelpError", f"Error in help command: {e}", user_id=message.from_user.id)


@dp.message(F.text == "ℹ️ Помощь")
async def help_button(message: Message):
    """Обработчик кнопки помощи"""
    await cmd_help(message)


@dp.message(Command("practice"))
@dp.message(F.text == "🎯 Практика")
async def cmd_practice(message: Message, state: FSMContext):
    """Обработчик начала практики"""
    try:
        session_id = await db.start_practice_session(message.from_user.id)
        await state.set_state(PracticeState.in_practice)
        await state.update_data(session_id=session_id, correct_answers=0, phrases_practiced=0)

        await log_message(db, message.from_user.id, session_id, "outgoing", "Начало сессии практики")
        await send_random_phrase(message, state)
    except Exception as e:
        await log_error(db, "PracticeError", f"Error starting practice: {e}", user_id=message.from_user.id)
        await message.answer("Произошла ошибка при запуске практики")


async def send_random_phrase(message: Message, state: FSMContext):
    """Отправляет случайную фразу для практики"""
    try:
        phrases = await db.get_all_phrases()
        if not phrases:
            await message.answer("Извините, фразы для практики временно недоступны")
            await state.clear()
            return

        import random
        phrase_row = random.choice(phrases)
        phrase = Phrase.from_db_row(phrase_row)

        await state.update_data(current_phrase_id=phrase.id, current_phrase_text=phrase.text)

        audio_file = FSInputFile(
            path=phrase.audio_path,
            filename="audio.wav"
        )

        await message.answer_voice(
            voice=audio_file,
            caption=f"🎧 Прослушайте фразу и дайте голосовой ответ", #\n\n<code>{phrase.text}</code>",
            reply_markup=practice_keyboard
        )

        await state.set_state(PracticeState.waiting_for_response)
        await log_message(db, message.from_user.id, (await state.get_data()).get('session_id'),
                          "outgoing", f"Аудиофраза: {phrase.text}")
    except Exception as e:
        await log_error(db, "SendPhraseError", f"Error sending phrase: {e}", user_id=message.from_user.id)
        await message.answer("Произошла ошибка при отправке фразы")


@dp.message(F.text == "🔁 Новая фраза")
async def new_phrase(message: Message, state: FSMContext):
    """Обработчик кнопки запроса новой фразы"""
    await send_random_phrase(message, state)


@dp.message(F.text == "⏹️ Завершить")
async def stop_practice(message: Message, state: FSMContext):
    """Обработчик завершения практики"""
    try:
        data = await state.get_data()
        session_id = data.get('session_id')
        correct_answers = data.get('correct_answers', 0)
        phrases_practiced = data.get('phrases_practiced', 0)

        if session_id:
            await log_practice_session(db, message.from_user.id, session_id, phrases_practiced, correct_answers)
            await log_message(db, message.from_user.id, session_id, "outgoing", "Завершение сессии практики")

        await state.clear()
        accuracy = round(correct_answers / phrases_practiced * 100, 2) if phrases_practiced > 0 else 0
        await message.answer(
            f"Практика завершена!\n\n"
            f"Фраз отработано: {phrases_practiced}\n"
            f"Правильных ответов: {correct_answers}\n"
            f"Точность: {accuracy}%",
            reply_markup=main_keyboard
        )
    except Exception as e:
        await log_error(db, "StopPracticeError", f"Error stopping practice: {e}", user_id=message.from_user.id)
        await message.answer("Произошла ошибка при завершении практики")


@dp.message(PracticeState.waiting_for_response, F.voice)
async def handle_voice_response(message: Message, state: FSMContext):
    """Обработчик голосовых сообщений с ответами пользователя"""
    voice = message.voice
    file_info = await bot.get_file(voice.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    with NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_ogg:
        tmp_ogg.write(downloaded_file.read())
        ogg_path = tmp_ogg.name

    wav_path = None
    recognized_text = ""
    try:
        data = await state.get_data()
        session_id = data.get('session_id')

        # Записываем факт получения голосового сообщения
        await log_message(db, message.from_user.id, session_id, "incoming", "Голосовое сообщение")

        try:
            wav_path = await convert_ogg_to_wav(ogg_path)
        except Exception as e:
            await message.answer("Ошибка конвертации аудио. Попробуйте еще раз.")
            await log_error(db, "AudioConversionError", f"Error converting audio: {e}", user_id=message.from_user.id)
            return

        recognized_text = recognize_speech_from_file(wav_path)

        # Записываем распознанный текст в историю диалогов
        if recognized_text:
            await log_message(db, message.from_user.id, session_id, "incoming", f"Распознанный текст: {recognized_text}")
        else:
            await log_message(db, message.from_user.id, session_id, "incoming", "Речь не распознана")

        if not recognized_text:
            await message.answer("Не удалось распознать речь. Попробуйте еще раз.")
            return

        phrase_id = data.get('current_phrase_id')
        phrase_text = data.get('current_phrase_text')

        success, explanation = await check_answer(db, phrase_id, recognized_text)

        phrases_practiced = data.get('phrases_practiced', 0) + 1
        correct_answers = data.get('correct_answers', 0)
        if success:
            correct_answers += 1

        await state.update_data(phrases_practiced=phrases_practiced, correct_answers=correct_answers)

        if success:
            await message.answer(f"✅ Отлично! \n\nВопрос: {phrase_text} \n\nВаш ответ: <i>{recognized_text}</i>\n\n{explanation}")
        else:
            await message.answer(
                f"❌ Нужно попробовать еще раз \n\nВопрос: {phrase_text}\n\nВаш ответ: <i>{recognized_text}</i>\n\n{explanation}")

        await log_message(db, message.from_user.id, session_id, "outgoing",
                          f"Результат проверки: {'True' if success else 'False'}. {explanation}")

        #await send_random_phrase(message, state)

    except Exception as e:
        await log_error(db, "VoiceProcessingError", f"Error processing voice: {e}", user_id=message.from_user.id)
        await message.answer("Произошла ошибка при обработке аудио")
    finally:
        # Удаляем временные файлы
        if os.path.exists(ogg_path):
            os.unlink(ogg_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


@dp.message(PracticeState.waiting_for_response, F.text)
async def handle_text_in_voice_mode(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений в режиме ожидания голосового ответа"""
    await message.answer("Пожалуйста, отправьте голосовое сообщение для ответа на фразу. "
                         "Или используйте кнопки меню для других действий.")


# Обработчики поддержки и статистики
@dp.message(Command("support"))
@dp.message(F.text == "❓ Поддержка")
async def cmd_support(message: Message, state: FSMContext):
    """Обработчик команды поддержки"""
    await state.set_state(SupportState.waiting_question)
    await message.answer(
        "Задайте ваш вопрос или выберите опцию:",
        reply_markup=support_keyboard
    )


@dp.message(F.text == "❓ Частые вопросы")
async def show_faq(message: Message):
    """Показывает частые вопросы"""
    faq_items = await db.get_all_faq()
    if not faq_items:
        await message.answer("Частые вопросы временно недоступны")
        return

    response = "❓ <b>Часто задаваемые вопросы:</b>\n\n"
    for i, (id, question, answer, keywords) in enumerate(faq_items, 1):
        response += f"{i}. <b>{question}</b>\n{answer}\n\n"

    await message.answer(response)


@dp.message(F.text == "👨‍💻 Оператор")
async def request_operator(message: Message, state: FSMContext):
    """Запрос связи с оператором"""
    if OPERATOR_ID:
        try:
            operator_message = (f"👤 Пользователь @{message.from_user.username or 'без username'} "
                                f"(ID: {message.from_user.id}) запросил помощь.\n\n"
                                f"Имя: {message.from_user.first_name or ''} "
                                f"{message.from_user.last_name or ''}\n\n"
                                f"Последнее сообщение: {message.text}")

            await bot.send_message(OPERATOR_ID, operator_message)
            await message.answer("✅ Ваш запрос передан оператору. Ожидайте ответа.")
            await log_message(db, message.from_user.id, None, "outgoing",
                              "Запрос передан оператору")
        except Exception as e:
            error_msg = f"Ошибка при отправке запроса оператору: {e}"
            await message.answer("❌ К сожалению, не удалось связаться с оператором. Попробуйте позже.")
            await log_error(db, "OperatorError", error_msg, user_id=message.from_user.id)
            logger.error(error_msg)
    else:
        await message.answer("К сожалению, оператор сейчас недоступен. Попробуйте позже.")

    await state.clear()
    await message.answer("Чем еще могу помочь?", reply_markup=main_keyboard)


@dp.message(SupportState.waiting_question, F.text == "🔙 Назад")
async def support_back(message: Message, state: FSMContext):
    """Обработчик кнопки назад в режиме поддержки"""
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_keyboard)


@dp.message(SupportState.waiting_question)
async def handle_support_question(message: Message, state: FSMContext):
    """Обработчик вопросов в поддержку"""
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовый вопрос")
        return

    response = await handle_user_query(db, message.text)

    if "извините" in response.lower():
        await message.answer(f"{response}\n\nХотите обратиться к оператору?",
                             reply_markup=support_keyboard)
    else:
        await message.answer(response)
        await state.clear()
        await message.answer("Чем еще могу помочь?", reply_markup=main_keyboard)


@dp.message(Command("stats"))
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Показывает статистику пользователя"""
    try:
        stats = await db.get_user_stats(message.from_user.id)
        await message.answer(
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"• Всего сессий: {stats['total_sessions']}\n"
            f"• Всего фраз: {stats['total_phrases']}\n"
            f"• Правильных ответов: {stats['total_correct']}\n"
            f"• Точность: {stats['accuracy']}%",
            reply_markup=main_keyboard
        )
        await log_message(db, message.from_user.id, None, "outgoing", "Статистика пользователя")
    except Exception as e:
        await log_error(db, "StatsError", f"Error getting stats: {e}", user_id=message.from_user.id)
        await message.answer("Произошла ошибка при получении статистики")


@dp.message(F.text == "🔙 Назад")
async def back_to_main(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_keyboard)


# Обработчик любых других сообщений
@dp.message()
async def handle_other_messages(message: Message):
    """Обработчик прочих сообщений"""
    await message.answer("Используйте кнопки меню для навигации", reply_markup=main_keyboard)


# Запуск бота
async def main():
    """Основная функция запуска бота"""
    try:
        await db.init_db()
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Закрытие соединения с БД
        # В текущей реализации нет метода close, но можно добавить при необходимости
        pass


if __name__ == "__main__":
    asyncio.run(main())