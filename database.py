import aiosqlite
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple, Dict, Any, AsyncGenerator
from config import DB_PATH, FAQ_DATA, PHRASES_DATA
import logging

# Настройка логирования для database модуля
logger = logging.getLogger(__name__)


class Database:
    """Класс для управления базой данных с использованием контекстных менеджеров."""

    def __init__(self, db_path: str = DB_PATH):
        """Инициализирует экземпляр базы данных."""
        self.db_path = db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Асинхронный контекстный менеджер для получения соединения с БД."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def execute_query(self, query: str, params: Tuple = None) -> Optional[Any]:
        """Выполняет запрос к базе данных и возвращает результат."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            await conn.commit()
            return cursor

    async def fetch_one(self, query: str, params: Tuple = None) -> Optional[Dict]:
        """Выполняет запрос и возвращает одну строку."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchone()

    async def fetch_all(self, query: str, params: Tuple = None) -> List[Dict]:
        """Выполняет запрос и возвращает все строки."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchall()

    async def init_db(self):
        """Инициализирует базу данных и создает таблицы при необходимости."""
        async with self.get_connection() as conn:
            # Создание таблицы phrases
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS phrases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL UNIQUE,
                    audio_path TEXT UNIQUE,
                    positive_keywords TEXT NOT NULL,
                    negative_keywords TEXT,
                    required_count INTEGER DEFAULT 2
                )
            ''')

            # Создание таблицы faq
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS faq (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    keywords TEXT NOT NULL
                )
            ''')

            # Таблица пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица сессий практики
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS practice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    phrases_practiced INTEGER DEFAULT 0,
                    correct_answers INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            # Таблица истории диалогов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS dialog_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id INTEGER,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (session_id) REFERENCES practice_sessions (id)
                )
            ''')

            # Таблица ошибок
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    traceback TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            # Проверяем, есть ли данные в таблицах
            cursor = await conn.execute('SELECT COUNT(*) as count FROM phrases')
            phrases_count = (await cursor.fetchone())['count']

            cursor = await conn.execute('SELECT COUNT(*) as count FROM faq')
            faq_count = (await cursor.fetchone())['count']

            # Добавляем начальные данные, если таблицы пустые
            if phrases_count == 0:
                for phrase in PHRASES_DATA:
                    await conn.execute(
                        '''INSERT INTO phrases 
                        (text, audio_path, positive_keywords, negative_keywords, required_count)
                        VALUES (?, ?, ?, ?, ?)''',
                        (phrase['text'], phrase['audio_path'],
                         #','.join(phrase['positive_keywords']),
                         #','.join(phrase['negative_keywords']) if phrase['negative_keywords'] else None,
                         phrase['positive_keywords'],
                         phrase['negative_keywords'] if phrase['negative_keywords'] else None,
                         phrase['required_count'])
                    )

            if faq_count == 0:
                for faq in FAQ_DATA:
                    await conn.execute(
                        'INSERT INTO faq (question, answer, keywords) VALUES (?, ?, ?)',
                        (faq['question'], faq['answer'], faq['keywords'])
                    )

            await conn.commit()
            logger.info("Database initialized successfully")

    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Добавление/обновление пользователя"""
        await self.execute_query(
            '''INSERT OR REPLACE INTO users (id, username, first_name, last_name, last_activity)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (user_id, username, first_name, last_name)
        )

    async def update_user_activity(self, user_id: int):
        """Обновление времени последней активности пользователя"""
        await self.execute_query(
            'UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE id = ?',
            (user_id,)
        )

    async def start_practice_session(self, user_id: int) -> int:
        """Начало новой сессии практики"""
        cursor = await self.execute_query(
            'INSERT INTO practice_sessions (user_id) VALUES (?)',
            (user_id,)
        )
        return cursor.lastrowid if cursor else None

    async def end_practice_session(self, session_id: int, phrases_practiced: int, correct_answers: int):
        """Завершение сессии практики"""
        await self.execute_query(
            '''UPDATE practice_sessions
            SET end_time = CURRENT_TIMESTAMP,
                phrases_practiced = ?,
                correct_answers = ?
            WHERE id = ?''',
            (phrases_practiced, correct_answers, session_id)
        )

    async def add_dialog_message(self, user_id: int, session_id: Optional[int],
                                 message_type: str, content: str):
        """Добавление сообщения в историю диалогов"""
        await self.execute_query(
            '''INSERT INTO dialog_history (user_id, session_id, message_type, content)
            VALUES (?, ?, ?, ?)''',
            (user_id, session_id, message_type, content)
        )

    async def log_error(self, error_type: str, error_message: str,
                        traceback: Optional[str] = None, user_id: Optional[int] = None):
        """Логирование ошибки"""
        await self.execute_query(
            '''INSERT INTO error_logs (error_type, error_message, traceback, user_id)
            VALUES (?, ?, ?, ?)''',
            (error_type, error_message, traceback, user_id)
        )

    async def get_user_stats(self, user_id: int) -> dict:
        """Получение статистики пользователя"""
        result = await self.fetch_one(
            '''SELECT COUNT(*) as total_sessions,
               SUM(phrases_practiced) as total_phrases,
               SUM(correct_answers) as total_correct,
               AVG(correct_answers * 1.0 / phrases_practiced) as accuracy
            FROM practice_sessions
            WHERE user_id = ? AND end_time IS NOT NULL''',
            (user_id,)
        )

        return {
            'total_sessions': result['total_sessions'] or 0,
            'total_phrases': result['total_phrases'] or 0,
            'total_correct': result['total_correct'] or 0,
            'accuracy': round(result['accuracy'] * 100, 2) if result['accuracy'] else 0
        }

    async def get_all_phrases(self):
        """Получает все фразы из базы данных."""
        rows = await self.fetch_all('SELECT * FROM phrases')
        return rows if rows else []

    async def get_phrase_by_id(self, phrase_id: int):
        """Получает фразу по ID."""
        row = await self.fetch_one('SELECT * FROM phrases WHERE id = ?', (phrase_id,))
        return row

    async def get_random_phrase(self):
        """Получает случайную фразу из базы данных."""
        row = await self.fetch_one('SELECT * FROM phrases ORDER BY RANDOM() LIMIT 1')
        return row

    async def get_all_faq(self):
        """Получает все записи FAQ из базы данных."""
        rows = await self.fetch_all('SELECT * FROM faq')
        return [(row['id'], row['question'], row['answer'], row['keywords']) for row in rows] if rows else []


# Глобальный экземпляр базы данных
db = Database()