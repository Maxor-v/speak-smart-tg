import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"bot_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Функции логирования будут принимать экземпляр db как параметр
async def log_message(db, user_id: int, session_id: int, message_type: str, content: str):
    """Логирование сообщения в БД"""
    try:
        await db.add_dialog_message(user_id, session_id, message_type, content)
        logger.info(f"User {user_id} - {message_type}: {content}")
    except Exception as e:
        logger.error(f"Error logging message: {e}")

async def log_error(db, error_type: str, error_message: str, traceback: str = None, user_id: int = None):
    """Логирование ошибки в БД и в файл"""
    try:
        await db.log_error(error_type, error_message, traceback, user_id)
        error_msg = f"{error_type}: {error_message}"
        if traceback:
            error_msg += f"\nTraceback: {traceback}"
        logger.error(error_msg)
    except Exception as e:
        logger.error(f"Error logging error: {e}")

async def log_practice_session(db, user_id: int, session_id: int, phrases_practiced: int, correct_answers: int):
    """Завершение сессии практики с результатами"""
    try:
        await db.end_practice_session(session_id, phrases_practiced, correct_answers)
        logger.info(f"User {user_id} completed session {session_id} with {correct_answers}/{phrases_practiced} correct answers")
    except Exception as e:
        await log_error(db, "SessionLogError", f"Error ending practice session: {e}", user_id=user_id)