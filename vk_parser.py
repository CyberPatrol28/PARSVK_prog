import os
import re
import time
from pathlib import Path

import vk_api

ITEMS_PER_PAGE = 30
REQUEST_DELAY = 1.2
BLACKLIST_PATH = os.getenv("BLACKLIST_PATH", "config/blacklist.txt")


# ---------- чёрный список ----------

def load_blacklist(path: str = BLACKLIST_PATH) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line.lower())
    return words


# ---------- токен ----------

def clean_token(token: str) -> str:
    """Убирает пробелы, переводы строк, кавычки, 'Bearer '."""
    if not token:
        return ""
    token = re.sub(r"\s+", "", token)
    token = token.strip("'\"")
    if token.lower().startswith("bearer"):
        token = token[6:]
    return token


def init_vk_api(token: str):
    token = clean_token(token)
    if not token:
        raise RuntimeError("Токен VK не задан")

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()

    try:
        vk.users.get(user_ids=1)
    except vk_api.exceptions.ApiError as e:
        code = getattr(e, "code", None)
        msg = getattr(e, "error_msg", str(e))
        if code == 5:
            raise RuntimeError(
                "VK: неверный access_token. Проверьте, что это user-токен "
                "(не сервисный) и он не отозван."
            ) from e
        raise RuntimeError(f"VK API {code}: {msg}") from e

    return vk


# ---------- поиск по ключевым словам ----------

def check_keywords_in_text(text, keywords):
    if not text:
        return []
    t = text.lower()
    return [kw for kw in keywords if kw.lower() in t]


def find_blacklist_hits(text: str, blacklist: list[str]) -> list[str]:
    if not text or not blacklist:
        return []
    t = text.lower()
    return [w for w in blacklist if w in t]


# ---------- ссылки ----------

def make_group_link(group):
    if group.get('screen_name'):
        return f"https://vk.com/{group['screen_name']}"
    return f"https://vk.com/club{group.get('id')}"


def make_user_link(user):
    if user.get('screen_name'):
        return f"https://vk.com/{user['screen_name']}"
    return f"https://vk.com/id{user.get('id')}"


# ---------- основной парсинг ----------

def parse_vk(keywords, count=ITEMS_PER_PAGE, progress_callback=None,
             token: str | None = None,
             blacklist=None, filtered_out=None):
    """
    token         — user-токен VK из веб-формы. Если None — берём env VK_TOKEN.
    blacklist     — список стоп-слов; None → load_blacklist().
    filtered_out  — список, куда складываются отброшенные (мутируется на месте).
    Возвращает список найденных записей.
    """
    token = clean_token(token or os.getenv("VK_TOKEN", ""))
    if not token:
        raise RuntimeError("Токен VK не передан (и VK_TOKEN в env не задан)")

    vk = init_vk_api(token)

    if blacklist is None:
        blacklist = load_blacklist()
    if filtered_out is None:
        filtered_out = []

    all_found_data = []
    total_steps = len(keywords) * 2
    step = 0

    for keyword in keywords:
        # ---------- Группы ----------
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, f"Поиск групп: '{keyword}'")

        try:
            results = vk.groups.search(q=keyword, count=count, sort=0)
            groups = results.get('items', [])
        except vk_api.exceptions.ApiError as e:
            print(f"[groups.search] {keyword}: {e}")
            groups = []

        for group in groups:
            name = group.get('name', '')
            description = group.get('description', '')
            full_text = f"{name} {description}"

            matched = check_keywords_in_text(full_text, keywords)
            if not matched:
                continue

            hits = find_blacklist_hits(full_text, blacklist)
            if hits:
                filtered_out.append({
                    'type': 'group',
                    'keyword': keyword,
                    'name': name,
                    'link': make_group_link(group),
                    'reason': 'blacklist',
                    'blacklist_hits': hits,
                })
                continue

            all_found_data.append({
                'type': 'group',
                'keyword': keyword,
                'matched_keywords': matched,
                'link': make_group_link(group),
                'name': name,
                'extra': f"Подписчиков: {group.get('members_count', 0)}; "
                         f"Описание: {description[:150]}",
            })

        time.sleep(REQUEST_DELAY)

        # ---------- Пользователи ----------
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, f"Поиск пользователей: '{keyword}'")

        try:
            results = vk.users.search(
                q=keyword, count=count,
                fields='about,status,interests,activities,screen_name',
            )
            users = results.get('items', [])
        except vk_api.exceptions.ApiError as e:
            print(f"[users.search] {keyword}: {e}")
            users = []

        for user in users:
            fn = user.get('first_name', '')
            ln = user.get('last_name', '')
            profile_text = " ".join(filter(None, [
                fn, ln,
                user.get('about', ''),
                user.get('status', ''),
                user.get('interests', ''),
                user.get('activities', ''),
            ]))

            matched = check_keywords_in_text(profile_text, keywords)
            if not matched:
                continue

            hits = find_blacklist_hits(profile_text, blacklist)
            if hits:
                filtered_out.append({
                    'type': 'user',
                    'keyword': keyword,
                    'name': f"{fn} {ln}".strip(),
                    'link': make_user_link(user),
                    'reason': 'blacklist',
                    'blacklist_hits': hits,
                })
                continue

            extra_parts = []
            for label, key in (("Статус", "status"),
                               ("О себе", "about"),
                               ("Интересы", "interests")):
                v = user.get(key, "")
                if v:
                    extra_parts.append(f"{label}: {v[:100]}")

            all_found_data.append({
                'type': 'user',
                'keyword': keyword,
                'matched_keywords': matched,
                'link': make_user_link(user),
                'name': f"{fn} {ln}".strip(),
                'extra': " | ".join(extra_parts),
            })

        time.sleep(REQUEST_DELAY)

    return all_found_data