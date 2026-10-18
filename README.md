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

## Структура

| Путь | Что |
|---|---|
| `service/app.py`, `service/jobs.py` | FastAPI: API для жюри (`X-API-Key`), веб-интерфейс, очередь задач с дедлайном 300 с от загрузки |
| `service/static/index.html` | веб-интерфейс: загрузка, статус, вердикт, кадры, таймкоды, нормы |
| `pipeline/analyze.py` | точка входа `analyze(video_path) -> list[Violation]` |
| `pipeline/real.py` | пайплайн: скан, уходы кассира, телефон/еда, посторонний, личные вещи, уход клиента |
| `pipeline/scene.py` | поиск стола кассира детектором (без привязки к ракурсу) |
| `pipeline/detect/` | детектор D-FINE (Objects365) |
| `pipeline/vlm/` | клиент к локальному llama-server (Qwen3-VL-8B) и промпты |
| `rules/catalog.yaml` | типы нарушений и нормативные источники (только сверенные с «Әділет») |
| `scripts/` | запуск, загрузка весов, оценка и проверки (ниже) |
| `docs/submission.md` | документация к сдаче: архитектура, типы, нормы, метрики, ограничения |
| `docs/` | обзор датасета, разметка типов командой, внешние данные |

Ответ API — схема из ТЗ (раздел 10); дополнительные поля `type_id`, `confidence`, `rule` её не нарушают.
Источник нормы попадает в ответ, только если в каталоге у него `verified: true`.

## Проверка качества и нагрузки

```bash
python scripts/eval.py --data open                      # метрики на 42 обучающих видео (нужен llama-server)
python scripts/eval.py --data open --only Х-1,Х-2       # выборочно
python scripts/smoke_api.py --key $KEY --video open/videos/X-1.mov            # API как у жюри + проверка схемы
python scripts/load_test.py --key $KEY --videos a.mov,b.mov,c.mov,d.mov,e.mov # несколько видео одновременно
python scripts/run_folder.py data/external/meva --expect no_violation        # чужие сцены
```

Итоговые цифры (v12): верный вердикт 28 из 42, найдено 16 из 22 нарушений, 20–60 с на видео,
5 видео одновременно — 228 с при лимите 300 с. Подробнее — [docs/submission.md](docs/submission.md).
