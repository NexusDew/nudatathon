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

## Модели

То же правило (FAQ 24): веса и код с Apache-2.0 / MIT (RT-DETR, RF-DETR, YOLOX) безопаснее, чем
AGPL-3.0 (Ultralytics YOLOv8/11): AGPL допускает коммерческое использование, но обязывает открыть код сервиса.

## Атрибуция

При использовании указать в [submission.md](submission.md): название датасета, автора, ссылку и лицензию
(CC BY требует атрибуции).
