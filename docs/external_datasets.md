# Внешние данные, похожие на наш кейс

Готового открытого датасета «касса банка + нарушения» нет: ни в статьях, ни на Roboflow / Hugging Face
не нашлось. Поэтому ниже — наборы под **отдельные типы** и под **другие ракурсы**. Проверено 17.10.2026.

## Соответствие регламенту

FAQ 7 разрешает открытые датасеты. FAQ 24 разрешает готовое только при лицензии, допускающей коммерческое
использование, а по FAQ 34 ForteBank может использовать решение коммерчески. Поэтому для обучения берём
**только данные с коммерческой лицензией**.

| Датасет | Лицензия | Для обучения | Комментарий |
|---|---|---|---|
| Open Images V7 | разметка CC BY 4.0, изображения CC BY 2.0 ([факты](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)) | **да**, с атрибуцией | Google не гарантирует лицензию каждого изображения |
| Roboflow: банкноты | CC BY 4.0 (по выдаче поиска) | **да**, после проверки страницы | атрибуция обязательна |
| Roboflow: People Using Cellphone | не проверена | пока нет | проверить на странице |
| Charades | Non-Commercial, «not … in a for-profit enterprise» | **нет** | максимум — разовая локальная проверка устойчивости; в решение не включать |
| Toyota Smarthome | только академическое использование | **нет** | — |
| RetailAction | кастомная лицензия Standard AI | **нет**, пока не прочитан LICENSE | — |
| ABODA | не указана (= все права защищены) | **нет** | — |

Модели — то же правило (FAQ 24): веса и код с Apache-2.0 / MIT (RT-DETR, RF-DETR, YOLOX) безопаснее,
чем AGPL-3.0 (Ultralytics YOLOv8/11): AGPL коммерческое использование допускает, но обязывает открыть код сервиса.

## Главное

| Датасет | Что даёт нам | Типы | Размер | Лицензия / доступ |
|---|---|---|---|---|
| [Charades](https://arxiv.org/abs/1604.01753) (AI2) | бытовые сцены в помещении, десятки разных ракурсов, покадровые интервалы действий | `phone_use`, `food_drink`, `unlocked_workstation` (закрыть ноутбук), `door_left_open`, `personal_items` | 9 848 видео ~30 с; 157 классов; 480p-архив 16,3 ГБ | **Non-Commercial**; разрешено «for evaluation purposes elsewhere»; без перераспространения. Прямая загрузка без регистрации |
| [RetailAction](https://huggingface.co/datasets/harpreetsahota/RetailAction) | **камеры на потолке** (2,5 м), руки берут/кладут предметы с полки, 2 ракурса на событие | `unattended_valuables`, `cash_left_in_client_zone` (руки + предмет) | 42 000 клипов, 600×600, 6 FPS, 28 ГБ (можно частично) | кастомная лицензия Standard AI (LICENSE в репозитории); загрузка через `fiftyone` |
| [ABODA](https://github.com/kevinlin311tw/ABODA) | оставленные предметы, в помещении и на улице, смена света | `unattended_valuables` | 11 видео | не указана; файлы лежат в репозитории |
| [Toyota Smarthome](https://project.inria.fr/toyotasmarthome/) | 7 камер в квартире, разные ракурсы, пожилые люди | `phone_use`, `food_drink`, ноутбук | 16 115 клипов, 31 класс, 640×480 | только академическое использование; заявка с рабочей или учебной почты (Gmail игнорируют), ответ до 3 дней |

### Классы Charades, которые нам нужны (обучающая часть, число интервалов)

| Наш тип | Классы Charades | Интервалов |
|---|---|---|
| `phone_use` | c015 Holding a phone · c016 Playing with a phone · c019 Talking on a phone | 1055 · 673 · 217 |
| `food_drink` | c106 Drinking from a cup/glass/bottle · c156 Someone is eating something · c065 Eating a sandwich | 1134 · 936 · 459 |
| `unlocked_workstation` | c046 Closing a laptop · c052 Working/Playing on a laptop | 100 · 341 |
| `door_left_open` | c006 Closing a door (+ c008 Opening, c097 Walking through a doorway) | 618 |
| `personal_items` | c022 Putting a bag somewhere | 280 |

Разметка уже скачана и проверена: `Charades.zip`, 3,5 МБ. Сами видео — отдельный архив `Charades_v1_480.zip`.

## Для детектора предметов (кадры, не видео)

- **COCO-предобученные модели** (YOLO и др.) уже знают `cell phone`, `laptop`, `cup`, `bottle`, `handbag`,
  `backpack`, `sandwich`, `person`. Отдельные данные под эти классы, скорее всего, не нужны.
- **[Open Images V7](https://storage.googleapis.com/openimages/web/index.html)**: боксы для `Mobile phone`, `Laptop`, `Coffee cup`,
  `Mug`, `Handbag`, `Door`, `Door handle`, `Coin`, `Human hand`. Класса «банкнота» **нет**.
- **Банкноты — Roboflow Universe:** например,
  [banknote-detection](https://universe.roboflow.com/bin-mibxd/banknote-detection-2amdt) (1 595 изображений, один класс)
  и [banknotes](https://universe.roboflow.com/areeya-that/banknotes-tynx8) (1 455). Лицензия по поиску CC BY 4.0,
  но страницы закрыты для автоматической загрузки — проверить вручную. Банкноты не тенге: годится только как «пачка бумаги в руке/на столе».
- **Телефон в руке — Roboflow:** [People Using Cellphone](https://universe.roboflow.com/projeto-integrador-j0c7l/people-using-cellphone)
  (~1 266 изображений; классы `cellphone`, `using cellphone`, `not using`). Ракурс и лицензию проверить на странице.

## Что не нашлось

- Датасеты с инкассацией, пересчётом денег кассиром, детектором подлинности, экраном блокировки — **нет**.
  Для `collection_handover`, `cash_count_without_client`, `cash_handling` и `unlocked_workstation`
  (экран блокировки или рабочий экран) остаются только наши съёмки ([shooting_plan.md](shooting_plan.md)).

## Как использовать

1. **Дообучение детектора предметов** (телефон, ноутбук, чашка, сумка, дверь, рука, пачки бумаги) —
   Open Images V7 + Roboflow с CC BY 4.0. Атрибуцию указать в документации к сдаче.
2. **Charades, Toyota Smarthome, RetailAction, ABODA — не использовать** ни для обучения, ни в составе решения.
3. Основной источник для «банковских» типов и для другого ракурса — свои съёмки ([shooting_plan.md](shooting_plan.md)).
