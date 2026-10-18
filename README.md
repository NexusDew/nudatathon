# Контроль кассовой дисциплины по видео — ForteBank Datathon 26

Локальный AI-сервис: принимает видео рабочего места кассира и возвращает признаки возможных
нарушений с таймкодом, кадрами-доказательствами и ссылкой на норматив РК.
Все модели работают локально, облачные AI-API не используются.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux: source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
python scripts/download_weights.py --dir D:/nudatathon_weights --only dfine,qwen8b,llamacpp
copy .env.example .env            # и задать API_KEY
```

Два окна PowerShell (не закрывать, пока сервис нужен):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1          # llama-server (Qwen3-VL-8B) + API/UI на 127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\tunnel_ngrok.ps1   # публичный адрес https://fiddling-uncheck-decency.ngrok-free.dev
```

UI: `http://localhost:8000/` (публично — адрес туннеля). Нужна видеокарта с 8 ГБ: перед запуском закрыть
игры и другие программы, занимающие видеопамять. Датасет положить в `open/` (`open/videos/*.mov`,
`open/open_labels.xlsx`), в git он не попадает. Документация к сдаче: [docs/submission.md](docs/submission.md).

## API

| Метод | Путь | |
|---|---|---|
| POST | `/api/v1/analyze` | multipart, поле `file` (.mov) → `{"job_id", "status": "processing"}` |
| GET | `/api/v1/jobs/{job_id}` | `processing` / `done` / `failed` + результат |

Заголовок `X-API-Key` обязателен, без него ответ 401.

```bash
curl -X POST http://localhost:8000/api/v1/analyze -H "X-API-Key: $KEY" -F "file=@video.mov"
curl http://localhost:8000/api/v1/jobs/<job_id> -H "X-API-Key: $KEY"
```

## Структура и владельцы

| Папка | Что | Роль |
|---|---|---|
| `service/` | FastAPI, очередь задач, веб-интерфейс | Backend и деплой |
| `pipeline/analyze.py` | точка входа `analyze(video_path) -> list[Violation]` | общий контракт |
| `pipeline/detect/`, `pipeline/rules/` | детектор, трекинг, правила по таймлайну | CV и правила |
| `pipeline/vlm/` | локальная VLM: проверка кандидатов, описания | VLM |
| `rules/catalog.yaml` | типы нарушений и нормативные источники | Нормативка |
| `scripts/eval.py` | метрики на обучающем датасете | все |
| `scripts/smoke_api.py` | проверка API как у жюри | Backend |
| `docs/` | обзор датасета, архитектура, ограничения | все |

### Контракты (менять только по договорённости)

1. **Ответ API** — схема из ТЗ, раздел 10. Доп. поля (`type_id`, `confidence`, `rule`) не мешают схеме.
2. **`analyze(video_path) -> list[Violation]`** (`pipeline/types.py`). Пустой список = `no_violation`.
3. **`rules/catalog.yaml`** — пайплайн ссылается только на `id` оттуда. Источник попадает в ответ,
   только если у него `verified: true` (сверен с adilet.zan.kz).

## Проверка качества

```bash
python scripts/eval.py --data open                 # все видео
python scripts/eval.py --data open --only Х-1,Х-2  # выборочно
python scripts/smoke_api.py --key $KEY --video open/videos/X-1.mov
```

Приоритет из FAQ: **пропуск нарушения недопустим**, ложных срабатываний — минимум.
Лимит 5 минут на видео считается с момента загрузки, поэтому при очереди из нескольких видео
цель — **< 45 с на видео**.

## Правила работы с git

- Ветки `feat/<область>`, маленькие PR в `main`.
- Не коммитить видео, датасет, веса и `.env`.
- Перед PR в пайплайн: прогнать `scripts/eval.py` и приложить итог.
