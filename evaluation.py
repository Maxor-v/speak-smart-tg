import asyncio
import os
import re
import speech_recognition as sr
from typing import Tuple
import logging
from models import Phrase
from config import FFMPEG_PATH

# Настройка логирования для evaluation модуля
logger = logging.getLogger(__name__)


async def convert_ogg_to_wav(ogg_path: str) -> str:
    """
    Конвертирует аудиофайл из формата OGG в WAV с использованием ffmpeg.
    Args:
        ogg_path (str): Путь к исходному OGG файлу
    Returns:
        str: Путь к сконвертированному WAV файлу
    Raises:
        Exception: Если конвертация не удалась
    """
    wav_path = ogg_path.replace('.ogg', '.wav')

    # Создаем процесс конвертации
    process = await asyncio.create_subprocess_exec(
        FFMPEG_PATH,
        '-i', ogg_path,
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        wav_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Ожидаем завершения процесса
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        raise Exception(f"FFmpeg error: {error_msg}")

    if not os.path.exists(wav_path):
        raise FileNotFoundError("Выходной WAV файл не был создан")

    return wav_path


def recognize_speech_from_file(audio_path: str, language: str = "ru-RU") -> str:
    """
    Распознает речь из аудиофайла с помощью Google Web Speech API.
    Args:
        audio_path (str): Путь к аудиофайлу
        language (str): Язык для распознавания (по умолчанию "ru-RU")
    Returns:
        str: Распознанный текст или пустая строка в случае ошибки
    """
    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data, language=language)
            return text
        except sr.UnknownValueError:
            logger.warning("Speech not recognized")
            return ""
        except sr.RequestError as e:
            logger.error(f"API request error: {e}")
            return ""

    except FileNotFoundError:
        logger.error(f"File not found: {audio_path}")
        return ""
    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        return ""


def normalize_text(text: str) -> list:
    """Приводит текст к нижнему регистру и разбивает на слова, удаляя лишние символы."""
    # Поддержка кириллицы и латиницы
    text = re.sub(r"[^\w\sа-яА-ЯёЁ]", " ", text.lower())
    return text.split()


async def check_answer(db, phrase_id: int, user_answer: str) -> Tuple[bool, str]:
    """
    Асинхронно проверяет ответ пользователя по ключевым словам из БД.
    Возвращает кортеж (успех, пояснение).
    """
    phrase_row = await db.get_phrase_by_id(phrase_id)
    if not phrase_row:
        return False, "Фраза не найдена"

    phrase = Phrase.from_db_row(phrase_row)

    words = normalize_text(user_answer)

    # Проверяем на наличие негативных ключевых слов
    for neg_word in phrase.negative_keywords:
        if neg_word and neg_word in words:
            return False, f"Обнаружено негативное слово: '{neg_word}'"

    # Считаем количество совпадений позитивных ключевых слов
    positive_count = 0
    found_keywords = []

    for pos_word in phrase.positive_keywords:
        if pos_word in words:
            positive_count += 1
            found_keywords.append(pos_word)

    # Проверяем, достаточно ли ключевых слов найдено
    if positive_count >= phrase.required_count:
        return True, f"Найдены ключевые слова: {', '.join(found_keywords)}"
    else:
        return False, f"Недостаточно ключевых слов. Найдено: {positive_count}, требуется: {phrase.required_count}"


async def get_faq_answer(db, user_question: str) -> str:
    """
    Ищет ответ в базе данных FAQ на основе вопроса пользователя.
    Args:
        db: Экземпляр базы данных
        user_question (str): Вопрос от пользователя.
    Returns:
        str: Найденный ответ или сообщение об отсутствии ответа.
    """
    user_question_lower = user_question.lower()
    faq_items = await db.get_all_faq()

    best_match = None
    max_keyword_matches = 0

    for _, question, answer, keywords in faq_items:
        keyword_list = [k.strip().lower() for k in keywords.split(',')]
        match_count = sum(1 for keyword in keyword_list if keyword in user_question_lower)

        if match_count > max_keyword_matches:
            max_keyword_matches = match_count
            best_match = answer

    return best_match if best_match else "Извините, я не нашел ответа в справке."


async def handle_user_query(db, user_input: str) -> str:
    """
    Обрабатывает ввод пользователя и возвращает ответ.
    Args:
        db: Экземпляр базы данных
        user_input (str): Текст, введенный пользователем.
    Returns:
        str: Ответ бота.
    """
    cleaned_input = user_input.strip()
    if not cleaned_input:
        return "Пожалуйста, задайте ваш вопрос."

    return await get_faq_answer(db, cleaned_input)