# Внешние данные, допустимые по регламенту

FAQ 7 разрешает открытые датасеты. FAQ 24 допускает готовое только с лицензией, разрешающей коммерческое
использование; по FAQ 34 ForteBank может использовать решение коммерчески. Поэтому здесь перечислены
**только источники с коммерческой лицензией**. Проверено 17.10.2026.

Готового открытого датасета «касса банка + нарушения» нет. Внешние данные годятся только для детектора
предметов; типы с действиями (еда, телефон в руке, инкассация, пересчёт) и другой ракурс — наши съёмки
([shooting_plan.md](shooting_plan.md)).

| Датасет | Что даёт | Лицензия | Статус |
|---|---|---|---|
| [Open Images V7](https://storage.googleapis.com/openimages/web/factsfigures_v7.html) | боксы: `Mobile phone`, `Laptop`, `Coffee cup`, `Mug`, `Handbag`, `Door`, `Door handle`, `Coin`, `Human hand` (банкнот нет) | разметка CC BY 4.0, изображения «listed as» CC BY 2.0 | можно, с атрибуцией и проверкой лицензии каждого изображения (ниже) |

Google пишет: «we make no representations or warranties regarding the license status of each image and
you should verify the license for each image yourself». Поэтому при выгрузке берём из метаданных
изображений колонку `License` и оставляем только CC BY 2.0; `OriginalURL` и `Author` сохраняем для атрибуции.

### Не подходит: Roboflow Universe

Даже наборы с пометкой CC BY 4.0 берём только с оговоркой. По [условиям Roboflow](https://roboflow.com/terms)
на бесплатном Public Plan сервис можно использовать «only … for your own internal, non-commercial use»
(разд. 2, 4a), а скачанное «cannot be re-hosted … without prior express permission from the dataset or content
author» (разд. 5). Для коммерческого решения — только платный план или прямое разрешение автора набора.
Банкнот в допустимых открытых наборах нет — купюры размечаем на своих кадрах.

## Видео с камер наблюдения: MEVA

[MEVA](https://mevadata.org/) — «Multiview Extended Video with Activities» (Kitware Inc., IARPA), лицензия
**CC BY 4.0** (файл LICENSE в репозитории `meva/meva-data-repo`). Камеры наблюдения с разных точек,
разметка действий. Взяты готовые примеры из публичного бакета `s3://mevadata-public-01/examples/videos/`.

Локально: `data/external/meva/` — 36 роликов `.mov` (6–36 с, 1920×1072, 25 FPS, 201 МБ), только сцены
в помещении: холл, кафетерий, коридор, спортзал. Уличные удалены. В git не коммитятся.

| Классы MEVA | Роликов | Ближайший наш тип |
|---|---|---|
| `talk-on-phone`, `text-on-phone` | 3 | `phone_use` (но это не кассир) |
| `laptop-interaction` | 3 | — |
| `purchasing` (продажа за столом) | 3 | ближе всего к кассе |
| `abandon-package`, `set-down-object`, `pick-up-object`, `theft` | 5 | `unattended_valuables` |
| `object-transfer`, `hand-interaction` | 5 | `unauthorized_access` (передача предмета) |
| `open-facility-door`, `enter/exit-through-structure` | 7 | `door_left_open` |
| `sit-down`, `stand-up`, `read-document` | 10 | уход / возврат |

**Чем это НЕ является.** Это общие планы залов: люди мелкие, стола кассира нет, в кадр вшиты рамки
разметки MEVA. Проверить «нашу кассу под другим углом» на них нельзя — для этого нужны свои съёмки.

**Зачем пригодится.**
1. Ложные срабатывания на незнакомой сцене: на всех 36 роликах ожидается `no_violation` и отсутствие падений.
2. Время обработки на 1920×1072 (в датасете 464×848).
3. `purchasing` — единственная сцена «человек за столом + подходящие клиенты».

Атрибуция: «Multiview Extended Video with Activities (MEVA) dataset by Kitware Inc. and IARPA, CC BY 4.0».

## Модели

То же правило (FAQ 24): веса и код с Apache-2.0 / MIT (RT-DETR, RF-DETR, YOLOX) безопаснее, чем
AGPL-3.0 (Ultralytics YOLOv8/11): AGPL допускает коммерческое использование, но обязывает открыть код сервиса.

## Атрибуция

При использовании указать в [submission.md](submission.md): название датасета, автора, ссылку и лицензию
(CC BY требует атрибуции).
