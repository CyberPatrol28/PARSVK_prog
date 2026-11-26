from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime

from vk_parser import parse_vk, load_blacklist

app = FastAPI(title="VK Parser")
templates = Jinja2Templates(directory="templates")

tasks_store: dict[str, dict] = {}


class ParseRequest(BaseModel):
    token: str = Field(..., min_length=10)   # токен приходит с формы
    keywords: List[str]
    count: int = 30
    blacklist: List[str] | None = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/parse")
async def start_parse(req: ParseRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    bl = req.blacklist if req.blacklist is not None else load_blacklist()

    # токен НЕ кладём в tasks_store — только передаём в функцию
    tasks_store[task_id] = {
        "status": "pending",
        "progress": 0,
        "total": len(req.keywords) * 2,
        "message": "Запуск...",
        "results": [],
        "filtered": [],
        "started_at": datetime.now().isoformat(),
        "keywords": req.keywords,
        "blacklist": bl,
    }

    def run_parse(token: str):
        def callback(step, total, message):
            tasks_store[task_id].update(
                progress=step, total=total,
                message=message, status="running",
            )
        try:
            filtered: list[dict] = []
            results = parse_vk(
                req.keywords, count=req.count,
                progress_callback=callback,
                token=token,
                blacklist=bl,
                filtered_out=filtered,
            )
            tasks_store[task_id]["results"] = results
            tasks_store[task_id]["filtered"] = filtered
            tasks_store[task_id].update(status="done", message="Готово")
        except Exception as e:
            tasks_store[task_id].update(status="error", message=str(e))
        finally:
            # токен выйдет из области видимости, когда функция завершится
            del token

    background_tasks.add_task(run_parse, req.token)
    return {"task_id": task_id}


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks_store:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    d = tasks_store[task_id]
    return {
        "status": d["status"],
        "progress": d["progress"],
        "total": d["total"],
        "message": d["message"],
        "results_count": len(d["results"]),
        "filtered_count": len(d.get("filtered", [])),
        "blacklist_size": len(d.get("blacklist", [])),
    }


@app.get("/api/results/{task_id}")
async def get_results(task_id: str):
    if task_id not in tasks_store:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    d = tasks_store[task_id]
    return {
        "status": d["status"],
        "results": d["results"],
        "filtered": d.get("filtered", []),
        "keywords": d["keywords"],
        "blacklist": d.get("blacklist", []),
        "started_at": d["started_at"],
    }


@app.get("/api/export/{task_id}")
async def export_results(task_id: str):
    if task_id not in tasks_store:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    d = tasks_store[task_id]

    lines = [
        "=" * 60,
        "РЕЗУЛЬТАТЫ ПАРСИНГА VK",
        f"Дата: {d['started_at']}",
        f"Ключевые слова ({len(d['keywords'])}): {', '.join(d['keywords'])}",
        f"Чёрный список ({len(d.get('blacklist', []))}): "
        f"{', '.join(d.get('blacklist', [])) or '—'}",
        f"Всего найдено: {len(d['results'])}",
        f"Отфильтровано чёрным списком: {len(d.get('filtered', []))}",
        "=" * 60 + "\n",
    ]

    by_kw: dict[str, list[dict]] = {}
    for item in d["results"]:
        by_kw.setdefault(item["keyword"], []).append(item)

    for kw, items in by_kw.items():
        lines.extend(["", "#" * 60, f"# КЛЮЧЕВОЕ СЛОВО: {kw}", "#" * 60])
        for it in items:
            lines.append(f"\n[{it['type'].upper()}] {it['link']}")
            lines.append(f"  Название: {it['name']}")
            if it.get("extra"):
                lines.append(f"  Инфо: {it['extra']}")
            lines.append(f"  Совпадения: {', '.join(it['matched_keywords'])}")

    filtered = d.get("filtered", [])
    if filtered:
        lines.extend(["", "#" * 60,
                      "# ОТФИЛЬТРОВАНО ЧЁРНЫМ СПИСКОМ", "#" * 60])
        for it in filtered:
            lines.append(f"\n[{it['type'].upper()}] {it['link']}")
            lines.append(f"  Название: {it['name']}")
            lines.append(f"  Стоп-слова: {', '.join(it.get('blacklist_hits', []))}")

    content = "\n".join(lines)
    return Response(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition":
                 f"attachment; filename=vk_results_{task_id[:8]}.txt"},
    )