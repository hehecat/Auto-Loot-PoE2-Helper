"""GUI окно настроек с трекбарами и чекбоксами (tkinter).

Открывается по хоткею или из трея. Позволяет менять параметры на лету
без ручного редактирования YAML. Сохраняет в текущий профиль.
"""
import tkinter as tk
from tkinter import ttk
import yaml
from pathlib import Path

from ..config_manager import load_config, DEFAULT_PATH
from ..core.profiles import PROFILES_DIR


class SettingsGUI:
    def __init__(self, on_apply=None):
        self.on_apply = on_apply
        self.root = None
        self._values = {}
        self._profile_path = None

    def open(self, current_cfg=None):
        """Открыть окно настроек."""
        if self.root and self.root.winfo_exists():
            self.root.lift()
            return

        self.root = tk.Tk()
        self.root.title("Auto Loot — Настройки")
        self.root.geometry("420x680")
        self.root.resizable(False, True)

        cfg = current_cfg or load_config(None)

        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0

        # --- Захват ---
        ttk.Label(frame, text="=== Захват ===", font=("Consolas", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 2))
        row += 1

        row = self._add_entry(frame, row, "Backend (dxcam/mss)", "capture.backend",
                              cfg.get("capture", {}).get("backend", "dxcam"))
        row = self._add_spin(frame, row, "Target FPS", "capture.target_fps",
                             cfg.get("capture", {}).get("target_fps", 30), 1, 120)
        row = self._add_check(frame, row, "Double Buffer", "capture.double_buffer",
                              cfg.get("capture", {}).get("double_buffer", False))

        # --- Видение ---
        ttk.Label(frame, text="=== Видение ===", font=("Consolas", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 2))
        row += 1

        row = self._add_spin(frame, row, "Min Blob Area", "vision.min_blob_area",
                             cfg.get("vision", {}).get("min_blob_area", 12), 1, 5000)
        row = self._add_spin(frame, row, "Hue Tolerance", "vision.hue_tolerance",
                             cfg.get("vision", {}).get("hue_tolerance", 8), 1, 50)
        row = self._add_spin(frame, row, "Sat Min", "vision.sat_min",
                             cfg.get("vision", {}).get("sat_min", 120), 0, 255)
        row = self._add_spin(frame, row, "Val Min", "vision.val_min",
                             cfg.get("vision", {}).get("val_min", 120), 0, 255)
        row = self._add_spin(frame, row, "Close Px", "vision.close_px",
                             cfg.get("vision", {}).get("close_px", 3), 0, 30)

        # --- Подбор ---
        ttk.Label(frame, text="=== Подбор ===", font=("Consolas", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 2))
        row += 1

        loot = cfg.get("loot", {})
        row = self._add_spin(frame, row, "Radius Px", "loot.pickup_radius_px",
                             loot.get("pickup_radius_px", 250), 50, 2000)
        row = self._add_spin(frame, row, "Cooldown Ms", "loot.click_cooldown_ms",
                             loot.get("click_cooldown_ms", 300), 10, 2000)
        row = self._add_spin(frame, row, "Dedup Ms", "loot.dedup_ms",
                             loot.get("dedup_ms", 2500), 0, 10000)
        row = self._add_spin(frame, row, "Lazy Radius", "loot.lazy_radius_px",
                             loot.get("lazy_radius_px", 80), 10, 500)
        row = self._add_combo(frame, row, "Mode", "loot.mode",
                              loot.get("mode", "toggle"), ["hold", "toggle", "single", "lazy"])

        # --- HP Flask ---
        ttk.Label(frame, text="=== HP Flask ===", font=("Consolas", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 2))
        row += 1

        hp = cfg.get("hp_flask", {})
        row = self._add_check(frame, row, "HP Enabled", "hp_flask.enabled",
                              hp.get("enabled", False))
        row = self._add_entry(frame, row, "HP Key", "hp_flask.key", hp.get("key", "1"))
        row = self._add_spin(frame, row, "HP Threshold", "hp_flask.threshold",
                             hp.get("threshold", 0.65), 0.1, 1.0, resolution=0.05)
        row = self._add_spin(frame, row, "HP Cooldown Ms", "hp_flask.cooldown_ms",
                             hp.get("cooldown_ms", 4500), 500, 15000)
        row = self._add_check(frame, row, "Sound", "hp_flask.sound",
                              hp.get("sound", True))

        # --- Оверлей ---
        ttk.Label(frame, text="=== Оверлей ===", font=("Consolas", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 2))
        row += 1

        ov = cfg.get("overlay", {})
        row = self._add_check(frame, row, "Overlay", "overlay.enabled",
                              ov.get("enabled", True))
        row = self._add_check(frame, row, "Tray Icon", "overlay.tray_icon",
                              ov.get("tray_icon", True))

        # --- Кнопки ---
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=15)

        ttk.Button(btn_frame, text="Применить", command=self._apply).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Сохранить в профиль", command=self._save_profile).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Закрыть", command=self.root.destroy).pack(side="left", padx=5)

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _add_entry(self, parent, row, label, key, value):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=str(value))
        entry = ttk.Entry(parent, textvariable=var, width=20)
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self._values[key] = var
        return row + 1

    def _add_spin(self, parent, row, label, key, value, from_, to_, resolution=1):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=float(value))
        spin = ttk.Spinbox(parent, from_=from_, to=to_, textvariable=var,
                           width=10, increment=resolution)
        spin.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self._values[key] = var
        return row + 1

    def _add_check(self, parent, row, label, key, value):
        var = tk.BooleanVar(value=bool(value))
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.grid(row=row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        self._values[key] = var
        return row + 1

    def _add_combo(self, parent, row, label, key, value, options):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        var = tk.StringVar(value=str(value))
        combo = ttk.Combobox(parent, textvariable=var, values=options, state="readonly", width=18)
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5, pady=2)
        self._values[key] = var
        return row + 1

    def _collect(self):
        """Собрать значения из GUI в dict конфига."""
        cfg = {}
        for key, var in self._values.items():
            parts = key.split(".")
            d = cfg
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            val = var.get()
            if isinstance(val, bool):
                d[parts[-1]] = val
            elif isinstance(val, float) and val == int(val) and "." not in str(var.get()):
                d[parts[-1]] = int(val)
            else:
                try:
                    d[parts[-1]] = int(val)
                except (ValueError, TypeError):
                    try:
                        d[parts[-1]] = float(val)
                    except (ValueError, TypeError):
                        d[parts[-1]] = str(val)
        return cfg

    def _apply(self):
        cfg = self._collect()
        if self.on_apply:
            self.on_apply(cfg)

    def _save_profile(self):
        cfg = self._collect()
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            initialdir=str(PROFILES_DIR),
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml")],
            title="Сохранить профиль"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Сгенерировано GUI настроек\n")
                yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
