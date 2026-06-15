# Auto Loot PoE2 Helper

Помощник авто-подбора лута для **Path of Exile 2**. Работает исключительно по скриншоту экрана — компьютерное зрение, без чтения памяти игры.

> ⚠️ Сторонняя автоматизация нарушает ToS GGG и может привести к бану аккаунта. Используешь на свой риск.

---

## Принцип работы

```
Лут-фильтр (NeverSink)
  │
  ├── filter_patcher.py — впрыскивает override-блок
  │     красит валюту/фрагменты/гемы/вейстоуны
  │     в уникальный цвет-маркер RGB(255,0,200) — ярко-розовый
  │     (такого цвета нет в окружении PoE2 → нет ложных срабатываний)
  │
  └── Игра рендерит подписи этим цветом
        │
        ▼
  capture/screen.py — захват кадра окна (dxcam 60fps)
        │
        ▼
  vision/color_detector.py — HSV-маска → поиск пикселей цвета-маркера → контуры → центры
        │
        ▼
  core/loot_engine.py — сортировка целей по приоритету (валюта > фрагменты > гемы > вейстоуны)
        │                фильтр по радиусу от центра экрана, очередь, анти-дабл-клик
        ▼
  input/mouse.py — геймерский бросок: быстро直线 к лейблу, точное приземление + клик
```

Главный цикл: **захват → детекция → сортировка → клик**. Всё, никакой магии.

---

## Возможности

### Подбор лута

Только «мелочёвка» — настраивается в `config/default.yaml`:

| Категория | Что подбирает |
|-----------|---------------|
| `currency` | Chaos Orb, Divine Orb, Exalted Orb и т.д. |
| `fragments` | Осколки, фрагменты карт |
| `gems` | Uncut Skill/Support/Spirit Gem |
| `waystones` | Вейстоуны для карт |

Уники, редкие вещи и белый мусор — **не подбираются**, берёшь сам.

**Приоритет:** валюта → фрагменты → гемы → вейстоуны. Внутри категории — ближайший к персонажу.

### Режимы подбора

| Режим | Описание |
|-------|----------|
| `toggle` | F8 вкл/выкл. Включил — собирает сам. |
| `hold` | Собирает, пока зажата клавиша `pickup` |
| `single` | Один клик за нажатие |
| `lazy` | Навёл мышь на лут — сам подбирает |

### Хоткеи

| Клавиша | Действие |
|---------|----------|
| F8 | Мастер вкл/выкл (авто-подбор + автоматика) |
| F7 | Сменить профиль (циклом) |
| F12 | Выход |

### Оверлей

Прозрачное click-through окно поверх игры:
- Статус: ON / idle, текущий режим и профиль
- Целей в кадре / в радиусе подбора
- Счётчик подобраного: `cur:47  frag:12  gem:3`
- HP% (если включена авто-фласка)

### Авто-фласка HP

Следит за орбом жизней через цветовую детекцию. Когда HP < порога — нажимает клавишу фласки.

```yaml
hp_flask:
  enabled: true
  key: "1"
  threshold: 0.65
  cooldown_ms: 4500
```

Самокалибровка: первые 6 секунд запоминает максимум (полный HP), нормирует относительно него.

### Авто-автоматика (по таймеру)

Секция `automation` в конфиге — фласки/скиллы по интервалу. По умолчанию выключена. Срабатывает только когда мастер F8 включён и окно игры в фокусе.

### Профили

`config/profiles/<name>.yaml` — переопределяют значения из `default.yaml`:

| Профиль | Назначение |
|---------|-----------|
| `calibrated` | Оптимальные настройки после калибровки |
| `mapping` | Увеличенный радиус подбора |
| `bossing` | Под боссов (свой радиус/приоритет) |

Смена на лету — F7. Старт с профилем: `--profile calibrated`.

### Патч фильтра

```powershell
python -m src.core.filter_patcher --check     # статус
python -m src.core.filter_patcher --patch     # впрыснуть override (бэкап → *.filter.bak)
python -m src.core.filter_patcher --unpatch   # откатить
```

После патча: Escape → Options → UI → перевыбрать фильтр в игре.

### Калибровка цвета

```powershell
python -m src.calibrate
python -m src.calibrate --target myprofile
```

- ЛКМ — взять цвет с экрана
- Shift+ЛКМ — указать центр персонажа
- Трекбары — допуск тона/насыщенности/яркости/площади/радиуса
- `s` — сохранить профиль
- `d` — сохранить debug-снимок в `_debug/`
- `q` — выход

---

## Установка

### Зависимости

```powershell
pip install -r requirements.txt
```

**Состав:**
- `dxcam` — быстрый захват экрана (DirectX)
- `opencv-python` + `numpy` — компьютерное зрение
- `pynput` — мышь/клавиатура + глобальные хоткеи
- `pywin32` — поиск окна PoE2, фокус
- `PyYAML` — конфиги
- `PyQt5` — прозрачный оверлей

### Запуск

```powershell
python -m src.main                          # стандартный запуск
python -m src.main --profile mapping        # с профилем
python -m src.main --no-overlay             # без оверлея
python -m src.main --calibrate              # окно калибровки с подсветкой целей
```

Или двойной клик по `run_calibrated.bat`.

### Тесты

```powershell
python -m pytest
```

---

## Структура проекта

```
Auto Loot PoE2 Helper/
├── config/
│   ├── default.yaml           # базовый конфиг
│   └── profiles/              # профили (calibrated, mapping, bossing)
├── src/
│   ├── main.py                # точка входа, главный цикл
│   ├── calibrate.py           # мастер калибровки цвета
│   ├── config_manager.py      # загрузка/мердж конфигов
│   ├── logger.py              # логирование
│   ├── capture/
│   │   ├── window.py          # поиск окна PoE2, геометрия, фокус
│   │   └── screen.py          # захват кадра (dxcam → mss fallback)
│   ├── vision/
│   │   ├── color_detector.py  # HSV-маска → детекция цвета-маркера
│   │   └── hp_detector.py     # детекция HP по цвету орба
│   ├── input/
│   │   ├── mouse.py           # геймерское движение + клик с рандомизацией
│   │   └── keyboard.py        # глобальные хоткеи
│   ├── core/
│   │   ├── loot_engine.py     # очередь целей, приоритеты, анти-дабл-клик
│   │   ├── filter_patcher.py  # впрыск override-блока в .filter
│   │   ├── hp_watcher.py      # мониторинг HP и авто-фласка
│   │   ├── automation.py      # авто-действия по таймеру
│   │   └── profiles.py        # загрузка/переключение профилей
│   └── ui/
│       └── overlay.py          # прозрачный оверлей поверх игры
├── tests/                     # pytest-тесты
├── tools/                     # дебаг-скрипты (анализ кадров, HP)
├── PLAN.md                    # план реализации
└── requirements.txt
```

---

## Конфигурация

Весь конфиг — `config/default.yaml`. Основные секции:

```yaml
filter:
  path: "C:/Users/OLD/Documents/My Games/Path of Exile 2/Vladislav Yoshi Perfection.filter"
  marker_rgb: [255, 0, 200]
  categories: [currency, fragments, gems, waystones]

vision:
  marker_hsv_low: [149, 200, 200]
  marker_hsv_high: [151, 255, 255]
  min_blob_area: 12

loot:
  pickup_radius_px: 400
  click_cooldown_ms: 90
  randomize_delay_ms: [20, 70]
  mode: toggle
  category_priority: [currency, fragments, gems, waystones]

hotkeys:
  toggle: "f8"
  pickup: "space"
  calibrate: "f9"
  quit: "f12"
```

Профили переопределяют только нужные поля — остальное берётся из `default.yaml`.

---

## Лицензия

MIT
