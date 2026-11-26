# 1. Установка
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Запуск
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 3. Открыть
# http://127.0.0.1:8000

# 4. Токен
# https://vkhost.github.io/

