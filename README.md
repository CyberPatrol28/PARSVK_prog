# 1. Установка
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Запуск
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 3. Открыть
# http://127.0.0.1:8000

# 4. Токен
# https://vkhost.github.io/ (быстро) или VK ID (официально)

# 5. Проверка токена
curl "https://api.vk.com/method/users.get?user_ids=1&access_token=ТОКЕН&v=5.199"
