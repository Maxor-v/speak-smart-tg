from dataclasses import dataclass
from typing import List

@dataclass
class Phrase:
    """Класс для представления фразы."""
    id: int
    text: str
    audio_path: str
    positive_keywords: List[str]
    negative_keywords: List[str]
    required_count: int

    @classmethod
    def from_db_row(cls, row):
        """Создает экземпляр Phrase из строки базы данных."""
        return cls(
            id=row['id'],
            text=row['text'],
            audio_path=row['audio_path'],
            positive_keywords=row['positive_keywords'].split(','),
            negative_keywords=row['negative_keywords'].split(',') if row['negative_keywords'] else [],
            required_count=row['required_count']
        )