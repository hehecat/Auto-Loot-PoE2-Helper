# Auto Loot PoE2 Helper — Отчёт по сессии

## Дата: 2025
## Задача: Интеграция джойстика DualSense для авто-подбора лута в PoE2

---

## Проблема

Игра Path of Exile 2 с подключённым DualSense:
- Игнорирует клавиатуру
- Игнорирует виртуальные Xbox контроллеры (vgamepad)
- Принимает ввод ТОЛЬКО от реального DualSense

Нужно: автоматически подбирать лут кнопкой X на DualSense.

---

## Пробованные методы

### 1. vgamepad (виртуальный Xbox 360 контроллер)
**Статус:** Не работает с DualSense

```python
import vgamepad as vg
gp = vg.VX360Gamepad()
gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gp.update()
```

**Результат:** Виртуальный Xbox создаётся, но PoE2 его не видит когда подключён DualSense. Игра читает только первый обнаруженный контроллер.

---

### 2. pynput (отправка клавиатуры)
**Статус:** Не работает в режиме контроллера

```python
from pynput.keyboard import Controller
kb = Controller()
kb.press('space')
kb.release('space')
```

**Результат:** PoE2 в режиме контроллера полностью игнорирует клавиатурный ввод.

---

### 3. win32api (отправка WM_KEYDOWN в окно)
**Статус:** Не работает

```python
import win32api, win32con
hwnd = win32gui.FindWindow(None, "Path of Exile 2")
win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, 0x20, 0)  # Space
```

**Результат:** PoE2 игнорирует синтетические клавиатурные сообщения в режиме контроллера.

---

### 4. pygame.event (фейковые события джойстика)
**Статус:** Не работает

```python
import pygame
ev = pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, button=0)
pygame.event.post(ev)
```

**Результат:** pygame.event.post() отправляет события только в очередь pygame, не на реальный контроллер.

---

### 5. Авто-отключение DualSense + vgamepad ✅
**Статус:** Работает (требует прав администратора)

```python
import subprocess
# Отключаем DualSense
subprocess.run(["powershell", "-Command", 
    "Get-PnpDevice -Class HIDClass | Where-Object {$_.FriendlyName -match 'DualSense'} | "
    "Disable-PnpDevice -Confirm:$false"])

# Создаём виртуальный Xbox
import vgamepad as vg
gp = vg.VX360Gamepad()
gp.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gp.update()

# Включаем DualSense обратно
subprocess.run(["powershell", "-Command",
    "Get-PnpDevice -Class HIDClass | Where-Object {$_.FriendlyName -match 'DualSense'} | "
    "Enable-PnpDevice -Confirm:$false"])
```

**Результат:** Работает! Игра видит виртуальный Xbox когда реальный DualSense отключён.

**Проблемы:**
- Требует прав администратора
- Задержка ~1-2 сек на отключение/включение
- Может нестабильно работать на некоторых системах

---

## Реализованное решение

### Архитектура

```
Bot Start
    │
    ├── Disable DualSense (PowerShell)
    ├── Wait 1s
    ├── Create Virtual Xbox 360 (vgamepad)
    │
    ├── Detect Loot ──► Press A Button ──► Loot Picked
    │
Bot Stop
    │
    ├── Reset Virtual Xbox
    └── Enable DualSense (PowerShell)
```

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `src/input/gamepad.py` | GamepadEmulator — эмуляция Xbox + управление DualSense |
| `tools/gamepad_emulator.py` | CLI для тестирования кнопок и стиков |
| `tools/gamepad_test.py` | Диагностика подключённого контроллера |
| `tools/gamepad_calibrate.py` | Калибровка маппинга кнопок |
| `config/gamepad/mapping.json` | Сохранённый маппинг кнопок |
| `config/default.yaml` | Конфиг с gamepad.enabled: true |

---

## Конфигурация

### config/default.yaml
```yaml
gamepad:
  enabled: true       # включить эмуляцию
  hp_button: "L2"     # кнопка HP фласки
  pickup_button: "X"  # кнопка подбора

hp_flask:
  input_method: gamepad  # keyboard | gamepad
```

### config/gamepad/mapping.json
```json
{
  "controller": "DualSense Wireless Controller",
  "buttons": {
    "pickup": 0,
    "hp_flask": 13,
    "mana_flask": 14,
    "dodge": 3,
    "skill_1": 2,
    "skill_2": 1
  }
}
```

---

## Тестирование

### Тест контроллера
```bash
python tools/gamepad_test.py
```
Показывает: DualSense Wireless Controller, 17 кнопок, 6 осей.

### Тест эмуляции
```bash
python tools/gamepad_emulator.py --button a
# Результат: Virtual Xbox 360 controller created, Button A pressed
```

---

## Ограничения

1. **Требуется администратор** для отключения/включения HID-устройств
2. **Задержка** ~1-2 сек при старте/остановке
3. **Нестабильность** на некоторых системах
4. **Нельзя эмулировать** нажатия кнопок на подключённом DualSense (аппаратное ограничение)

---

## Рекомендации

1. Запускать бота от имени администратора
2. Использовать `run_gui.bat` для запуска
3. Калибровать кнопки через `gamepad_calibrate.py`
4. Проверять статус в GUI (Dashboard → Gamepad status)
