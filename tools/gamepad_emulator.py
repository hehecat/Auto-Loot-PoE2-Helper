"""Эмуляция кнопок и стиков Xbox контроллера через vgamepad.

Использование:
    python gamepad_emulator.py                      # интерактивный режим
    python gamepad_emulator.py --button a           # нажать кнопку A
    python gamepad_emulator.py --button x --hold 0.5  # зажать X на 0.5 сек
    python gamepad_emulator.py --stick left 0 1     # левый стик вверх
    python gamepad_emulator.py --stick left 1 0     # левый стик вправо
    python gamepad_emulator.py --stick right -0.5 0.5  # правый стик
    python gamepad_emulator.py --list               # список кнопок и команд
"""
import argparse
import time
import sys

try:
    import vgamepad as vg
except ImportError:
    print("Ошибка: vgamepad не установлен.")
    print("Установи: pip install vgamepad")
    sys.exit(1)

# Маппинг кнопок
BUTTONS = {
    "a": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "b": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "x": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "lb": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "rb": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "lt": "trigger_left",
    "rt": "trigger_right",
    "back": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "start": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "guide": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "ls": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "rs": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "up": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "down": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "left": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "right": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}


def list_buttons():
    print("Доступные кнопки:")
    print("-" * 30)
    for name in BUTTONS:
        print(f"  {name:10s}")
    print()
    print("Аналоговые стики:")
    print("  left X Y    - левый стик (X, Y: -1.0..1.0)")
    print("  right X Y   - правый стик (X, Y: -1.0..1.0)")
    print()
    print("Примеры:")
    print("  python gamepad_emulator.py --button a")
    print("  python gamepad_emulator.py --button x --hold 0.5")
    print("  python gamepad_emulator.py --stick left 0 1")
    print("  python gamepad_emulator.py --stick right 0.5 -0.5")


def press_button(gamepad, button_name, hold_time=0.1):
    """Нажать и отпустить кнопку."""
    if button_name not in BUTTONS:
        print(f"Неизвестная кнопка: {button_name}")
        print(f"Доступные: {', '.join(BUTTONS.keys())}")
        return False

    btn = BUTTONS[button_name]

    if btn == "trigger_left":
        gamepad.left_trigger(value=255)
        gamepad.update()
        time.sleep(hold_time)
        gamepad.left_trigger(value=0)
        gamepad.update()
        print(f"TRIGGER LEFT нажат на {hold_time}с")
    elif btn == "trigger_right":
        gamepad.right_trigger(value=255)
        gamepad.update()
        time.sleep(hold_time)
        gamepad.right_trigger(value=0)
        gamepad.update()
        print(f"TRIGGER RIGHT нажат на {hold_time}с")
    else:
        gamepad.press_button(button=btn)
        gamepad.update()
        time.sleep(hold_time)
        gamepad.release_button(button=btn)
        gamepad.update()
        print(f"Кнопка {button_name.upper()} нажата на {hold_time}с")

    return True


def move_stick(gamepad, stick, x, y, hold_time=0.0):
    """Двинуть аналоговый стик в позицию (x, y: -1.0..1.0)."""
    # Нормализация значений
    x = max(-1.0, min(1.0, float(x)))
    y = max(-1.0, min(1.0, float(y)))

    # Конвертация в 16-битное значение (-32768..32767)
    x_int = int(x * 32767)
    y_int = int(y * 32767)

    if stick == "left":
        gamepad.left_joystick(x_value=x_int, y_value=y_int)
    elif stick == "right":
        gamepad.right_joystick(x_value=x_int, y_value=y_int)
    else:
        print(f"Неизвестный стик: {stick}. Доступные: left, right")
        return False

    gamepad.update()
    print(f"Стик {stick}: X={x:.2f} Y={y:.2f}")

    if hold_time > 0:
        time.sleep(hold_time)
        # Возврат в центр
        if stick == "left":
            gamepad.left_joystick(x_value=0, y_value=0)
        else:
            gamepad.right_joystick(x_value=0, y_value=0)
        gamepad.update()
        print(f"Стик {stick} возвращён в центр")

    return True


def center_sticks(gamepad):
    """Вернуть оба стика в центр."""
    gamepad.left_joystick(x_value=0, y_value=0)
    gamepad.right_joystick(x_value=0, y_value=0)
    gamepad.left_trigger(value=0)
    gamepad.right_trigger(value=0)
    gamepad.update()
    print("Все стики и триггеры в центре")


def interactive_mode():
    """Интерактивный режим с вводом команд."""
    gamepad = vg.VX360Gamepad()
    print("Виртуальный Xbox контроллер создан.")
    print("Команды:")
    print("  кнопка           - нажать кнопку (a, b, x, y, lt, rt, ...)")
    print("  кнопка время     - зажать кнопку (x 0.5)")
    print("  stick left X Y   - левый стик (-1.0..1.0)")
    print("  stick right X Y  - правый стик (-1.0..1.0)")
    print("  center           - все стики в центр")
    print("  выход            - выход")
    print("-" * 40)

    while True:
        try:
            cmd = input("\n> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break

        if not cmd or cmd == "выход" or cmd == "exit" or cmd == "q":
            break

        parts = cmd.split()

        if parts[0] == "stick" and len(parts) == 4:
            # stick left X Y
            stick = parts[1]
            x = float(parts[2])
            y = float(parts[3])
            move_stick(gamepad, stick, x, y)
        elif parts[0] == "center":
            center_sticks(gamepad)
        else:
            # Кнопка
            button = parts[0]
            hold = float(parts[1]) if len(parts) > 1 else 0.1
            press_button(gamepad, button, hold)

    # Сброс при выходе
    center_sticks(gamepad)
    print("Контроллер сброшен.")


def main():
    parser = argparse.ArgumentParser(description="Эмуляция Xbox контроллера")
    parser.add_argument("--button", "-b", help="Кнопка для нажатия (a, b, x, y, lt, rt, ...)")
    parser.add_argument("--hold", "-t", type=float, default=0.1, help="Время удержания (сек)")
    parser.add_argument("--stick", nargs=3, metavar=("STICK", "X", "Y"),
                        help="Двинуть стик: left/right X Y (значения -1.0..1.0)")
    parser.add_argument("--list", "-l", action="store_true", help="Показать список кнопок и команд")
    parser.add_argument("--count", "-c", type=int, default=1, help="Количество нажатий")
    parser.add_argument("--interval", "-i", type=float, default=0.5, help="Интервал между нажатиями (сек)")

    args = parser.parse_args()

    if args.list:
        list_buttons()
        return

    if args.button or args.stick:
        gamepad = vg.VX360Gamepad()
        print(f"Создан виртуальный Xbox контроллер")

        if args.button:
            for i in range(args.count):
                if args.count > 1:
                    print(f"\n--- Нажатие {i+1}/{args.count} ---")
                press_button(gamepad, args.button, args.hold)
                if i < args.count - 1:
                    time.sleep(args.interval)

        if args.stick:
            stick, x, y = args.stick
            move_stick(gamepad, stick, float(x), float(y), hold_time=0.5)

        gamepad.reset()
        gamepad.update()
        print("\nГотово.")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
