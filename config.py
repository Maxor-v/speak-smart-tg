import os

TELEGRAM_BOT_TOKEN=""
TELEGRAM_OPERATOR_ID=""


# Конфигурация путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'speech_trainer.db')
MEDIA_DIR = os.path.join(BASE_DIR, 'media')
os.makedirs(MEDIA_DIR, exist_ok=True)

FFMPEG_PATH = os.getenv("FFMPEG_PATH", r"C:\ffmpeg\bin\ffmpeg.exe")

# Данные для инициализации таблицы FAQ
FAQ_DATA = [
    {
        "question": "Как начать практику?",
        "answer": "Чтобы начать языковую сессию, просто отправьте команду /practice. Бот отправит вам голосовое сообщение с фразой, на которую вам нужно будет ответить также голосовым сообщением.",
        "keywords": "начать,старт,практика,как начать,/practice,команда"
    },
    {
        "question": "Бот не распознает мой голосовой ответ. Что делать?",
        "answer": "Убедитесь, что вы говорите четко и достаточно громко, рядом нет фонового шума. Попробуйте перезапустить сессию командой /practice и записать ответ еще раз. Если проблема повторяется, возможно, возникли временные неполадки с сервисом распознавания речи.",
        "keywords": "не распознает,не слышит,проблема,голос,ошибка,не работает,что делать"
    },
    {
        "question": "Как работает проверка ответов?",
        "answer": "Бот не требует идеального повторения фразы. Он ищет в вашем ответе ключевые слова, соответствующие эталонной фразе. Главное — уловить смысл и использовать правильную лексику. Это помогает практиковать разговорную речь в более естественной манере.",
        "keywords": "проверка,как проверяет,ключевые слова,эталон,работает,алгоритм"
    },
    {
        "question": "Можно ли поменять сложность или тему практики?",
        "answer": "В текущей версии темы и сложность задаются автоматически. В будущих обновлениях мы обязательно добавим возможность выбора. Следите за новостями!",
        "keywords": "сложность,тема,уровень,поменять,выбор,настройки,сложно,легко"
    },
    {
        "question": "Что делать, если я не нашел ответ на свой вопрос?",
        "answer": "Если ответа нет в списке часто задаваемых вопросов, вы можете переадресовать свой вопрос живому оператору. Просто напишите свой вопрос, и бот предложит вам такую возможность.",
        "keywords": "оператор,человек,помощь,другой вопрос,не нашел,справка,связь"
    }
]

# Данные для инициализации таблицы фраз
PHRASES_DATA = [
    {
        "text": "Hello! How are you today?",
        "audio_path": "media/Hello How are you to.wav",
        "positive_keywords": "hello,hi,hey,i'm,good,fine,great,okay,well,thanks,thank you",
        "negative_keywords": "",
        "required_count": 2
    },
    {
        "text": "What is your name?",
        "audio_path": "media/What is your name.wav",
        "positive_keywords": "my,name,is,i'm,called",
        "negative_keywords": "",
        "required_count": 2
    },
    {
        "text": "Do you like music?",
        "audio_path": "media/Do you like music.wav",
        "positive_keywords": "yes,i,do,like,love,enjoy,music",
        "negative_keywords": "no,not,don't,hate",
        "required_count": 2
    },
    {
        "text": "What did you do yesterday?",
        "audio_path": "media/What did you do yest.wav",
        "positive_keywords": "yesterday,i,watched,listened,played,read,worked,did",
        "negative_keywords": "",
        "required_count": 2
    },
    {
        "text": "What are your plans for the weekend?",
        "audio_path": "media/What are your plans.wav",
        "positive_keywords": "weekend,i,will,am,going,to,plan,plans,want",
        "negative_keywords": "",
        "required_count": 2
    }
]