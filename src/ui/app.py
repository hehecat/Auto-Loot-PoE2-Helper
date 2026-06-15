"""Полноценное GUI приложение Auto Loot PoE2 Helper (PyQt5).

Вкладки:
  Dashboard  — статус в реальном времени
  Profiles   — управление профилями
  Settings   — все настройки
  Stats      — статистика сессии
  Logs       — логи в реальном времени
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QGroupBox, QFormLayout, QComboBox, QSpinBox,
        QDoubleSpinBox, QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem,
        QHeaderView, QSplitter, QFrame, QProgressBar, QSlider, QLineEdit,
        QMessageBox, QFileDialog, QSystemTrayIcon, QMenu, QAction, QScrollArea,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt5.QtGui import QFont, QColor, QIcon, QPalette
    HAS_PYQT5 = True
except ImportError:
    HAS_PYQT5 = False

from ..config_manager import load_config, DEFAULT_PATH
from ..core.profiles import ProfileManager, PROFILES_DIR


# === Стиль ===
DARK_STYLE = """
QMainWindow { background: #1a1a2e; }
QTabWidget::pane { border: 1px solid #2a2a4a; background: #16213e; }
QTabBar::tab { background: #0f3460; color: #e0e0e0; padding: 10px 20px;
               border: 1px solid #2a2a4a; border-bottom: none; border-radius: 4px 4px 0 0; }
QTabBar::tab:selected { background: #16213e; color: #00ff88; }
QTabBar::tab:hover { background: #1a1a4e; }
QGroupBox { border: 1px solid #2a2a4a; border-radius: 6px; margin-top: 10px;
            padding-top: 15px; color: #e0e0e0; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #00ff88; }
QLabel { color: #ffffff; }
QLabel#header { color: #00ff88; font-size: 18px; font-weight: bold; }
QLabel#status-on { color: #00ff88; font-size: 14px; font-weight: bold; }
QLabel#status-off { color: #ff4444; font-size: 14px; font-weight: bold; }
QPushButton { background: #0f3460; color: #ffffff; border: 1px solid #2a2a4a;
              padding: 8px 16px; border-radius: 4px; }
QPushButton:hover { background: #1a1a4e; }
QPushButton:pressed { background: #00ff88; color: #000; }
QPushButton:disabled { background: #1a1a2e; color: #555; }
QPushButton#danger { background: #8b0000; color: #ffffff; }
QPushButton#danger:hover { background: #a00000; }
QPushButton#success { background: #006400; color: #ffffff; }
QPushButton#success:hover { background: #008000; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #0f3460; color: #ffffff;
    border: 1px solid #2a2a4a; padding: 5px; border-radius: 3px; }
QTextEdit { background: #0a0a1a; color: #00ff88; font-family: Consolas; border: 1px solid #2a2a4a; }
QTableWidget { background: #0f3460; color: #ffffff; gridline-color: #2a2a4a; }
QTableWidget::item { color: #ffffff; }
QHeaderView::section { background: #16213e; color: #00ff88; padding: 5px; border: 1px solid #2a2a4a; }
QProgressBar { border: 1px solid #2a2a4a; border-radius: 4px; text-align: center; color: #000; }
QProgressBar::chunk { background: #00ff88; border-radius: 3px; }
QCheckBox { color: #ffffff; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #2a2a4a; border-radius: 3px; background: #0f3460; }
QCheckBox::indicator:checked { background: #00ff88; border-color: #00ff88; }
QCheckBox::indicator:unchecked { background: #0f3460; }
QSlider::groove:horizontal { background: #2a2a4a; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #00ff88; width: 16px; margin: -5px 0; border-radius: 8px; }
QScrollArea { border: none; }
QWidget { color: #ffffff; }
"""


class BotRunner:
    """Управление ботом: запуск/остановка в фоновом потоке."""

    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self._status = {}
        self._lock = threading.Lock()
        self._radius = 250

    @property
    def running(self):
        return self._running

    def start(self, cfg, profile_name="default"):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._profile = profile_name
        self._radius = cfg.get("loot", {}).get("pickup_radius_px", 250)
        self._thread = threading.Thread(target=self._run_bot, args=(cfg,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._running = False
        self._update_status(active=False)

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def get_overlay_state(self):
        with self._lock:
            return {
                "radius": self._radius,
                "active": self._status.get("active", False),
                "targets": self._status.get("targets", 0),
                "in_radius": self._status.get("in_radius", 0),
                "center_offset": self._status.get("center_offset", [0, 0]),
                "frame_size": self._status.get("frame_size", [1920, 1080]),
            }

    def _update_status(self, **kw):
        with self._lock:
            self._status.update(kw)

    def _run_bot(self, cfg):
        import cv2
        from ..capture.screen import ScreenCapture
        from ..capture.window import GameWindow
        from ..core.loot_engine import LootEngine
        from ..core.hp_watcher import HPWatcher
        from ..core.pickup_logger import PickupLogger
        from ..core.stats import StatsCollector
        from ..input.mouse import Mouse
        from ..vision.color_detector import ColorDetector

        log = logging.getLogger("autoloot.gui")
        self._update_status(mode=cfg.get("loot", {}).get("mode", "toggle"),
                            profile=getattr(self, '_profile', 'default'), active=True)

        try:
            win = GameWindow(cfg["game"]["window_title"])
            region = None
            if win.find():
                region = win.get_region()
            if not region:
                from ..capture.window import GameWindow as GW
                region = GW.primary_region()

            cap = ScreenCapture(cfg["capture"]["backend"],
                                double_buffer=cfg["capture"].get("double_buffer", False))
            loot = cfg["loot"]
            mouse = Mouse(rand_delay_ms=tuple(loot.get("randomize_delay_ms", [20, 70])),
                          human_move=loot.get("human_mouse", True))

            gamepad = None
            if cfg.get("gamepad", {}).get("enabled", False):
                try:
                    from ..input.gamepad import GamepadEmulator
                    gamepad = GamepadEmulator()
                    if gamepad.enabled:
                        log.info("Gamepad: ACTIVE - mapping loaded")
                    else:
                        log.warning("Gamepad: FAILED to initialize")
                        gamepad = None
                except Exception as e:
                    log.error("Gamepad error: %s", e)
                    gamepad = None

            engine = LootEngine(
                mouse=mouse, region=region,
                center_offset=loot.get("center_offset_xy", [0, 0]),
                radius=loot["pickup_radius_px"],
                cooldown_ms=loot.get("click_cooldown_ms", 90),
                log=log, dedup_px=loot.get("dedup_px", 24),
                dedup_ms=loot.get("dedup_ms", 0),
                stuck_timeout_s=loot.get("stuck_timeout_s", 5.0),
                roi_margin_px=loot.get("roi_margin_px", 100),
                gamepad=gamepad,
            )

            v = cfg.get("vision", {})
            cat_map = cfg.get("filter", {}).get("category_colors", {})
            det = ColorDetector(
                markers=[cfg["filter"]["marker_rgb"]] + [c for c in cat_map.values() if c],
                hue_tol=v.get("hue_tolerance", 8), sat_min=v.get("sat_min", 120),
                val_min=v.get("val_min", 120), min_blob_area=v.get("min_blob_area", 12),
                close_px=v.get("close_px", 3),
            )

            hp_watcher = HPWatcher(cfg.get("hp_flask", {}), log)
            if gamepad and gamepad.enabled:
                hp_watcher.set_gamepad(gamepad)

            pickup_log = PickupLogger()
            stats_collector = StatsCollector()
            stats_collector.start_session()

            target_fps = max(1, cfg["capture"].get("target_fps", 30))
            frame_budget = 1.0 / target_fps
            picked = 0
            stats = {}

            if cap._double_buffer:
                cap.start_buffer(region, target_fps)

            try:
                while not self._stop_event.is_set():
                    t0 = time.perf_counter()
                    frame = cap.grab(region)
                    if frame is None:
                        time.sleep(frame_budget)
                        continue

                    roi = engine.get_roi(frame.shape)
                    if roi:
                        x1, y1, x2, y2 = roi
                        detect_frame = frame[y1:y2, x1:x2]
                        roi_offset = (x1, y1)
                    else:
                        detect_frame = frame
                        roi_offset = (0, 0)

                    points, mask = det.detect(detect_frame)
                    if roi:
                        points = [(x + roi_offset[0], y + roi_offset[1], a)
                                  for x, y, a in points]
                    in_radius = engine.targets_in_radius(points, frame.shape)

                    foreground = win.is_foreground()
                    if in_radius and foreground:
                        result = engine.pick_once(points, frame.shape)
                        if result:
                            tx, ty = result
                            picked += 1
                            cat = "?"
                            if cat_map:
                                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                                from ..main import category_for_pixel
                                cat = category_for_pixel(
                                    hsv, tx, ty, cat_map,
                                    v.get("hue_tolerance", 8),
                                    v.get("sat_min", 120), v.get("val_min", 120))
                            stats[cat] = stats.get(cat, 0) + 1
                            stats_collector.record(cat, region["left"] + tx, region["top"] + ty)

                    if hp_watcher:
                        hp_watcher.check(frame, foreground)

                    self._update_status(
                        targets=len(points), in_radius=len(in_radius),
                        active=True, picked=picked,
                        foreground=foreground, stats=dict(stats),
                        hp=round(hp_watcher.hp_ratio * 100) if hp_watcher else None,
                        mode=loot.get("mode", "toggle"),
                        radius=self._radius,
                        center_offset=engine.center_offset,
                        frame_size=[frame.shape[1], frame.shape[0]],
                        session_stats=f"{stats_collector.session.total} items ({stats_collector.session.picks_per_minute:.0f}/min)",
                    )

                    elapsed = time.perf_counter() - t0
                    if elapsed < frame_budget:
                        time.sleep(frame_budget - elapsed)
            finally:
                if cap._double_buffer:
                    cap.stop_buffer()
                pickup_log.close()
        except Exception as e:
            log.error("Bot error: %s", e)
        finally:
            self._running = False
            self._update_status(active=False)


if HAS_PYQT5:

    class Signals(QObject):
        status_update = pyqtSignal(dict)
        log_message = pyqtSignal(str)

    class DashboardTab(QWidget):
        def __init__(self, signals, bot):
            super().__init__()
            self.signals = signals
            self.bot = bot
            self._main_window = None
            self._setup_ui()
            self.signals.status_update.connect(self._update_status)

        def set_main_window(self, win):
            self._main_window = win

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            header = QLabel("AUTO LOOT POE2 HELPER")
            header.setObjectName("header")
            header.setAlignment(Qt.AlignCenter)
            layout.addWidget(header)

            self.status_label = QLabel("STOPPED")
            self.status_label.setObjectName("status-off")
            self.status_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.status_label)

            stats_group = QGroupBox("Stats")
            stats_layout = QFormLayout()
            self.mode_label = QLabel("-")
            self.profile_label = QLabel("default")
            self.targets_label = QLabel("0")
            self.radius_label = QLabel("0")
            self.picked_label = QLabel("0")
            self.session_label = QLabel("-")
            self.hp_label = QLabel("-")
            self.cat_label = QLabel("all")

            stats_layout.addRow("Mode:", self.mode_label)
            stats_layout.addRow("Profile:", self.profile_label)
            stats_layout.addRow("Targets:", self.targets_label)
            stats_layout.addRow("In radius:", self.radius_label)
            stats_layout.addRow("Picked:", self.picked_label)
            stats_layout.addRow("Category:", self.cat_label)
            stats_layout.addRow("Session:", self.session_label)
            stats_layout.addRow("HP:", self.hp_label)
            stats_group.setLayout(stats_layout)
            layout.addWidget(stats_group)

            btn_layout = QHBoxLayout()
            self.start_btn = QPushButton("START")
            self.start_btn.setObjectName("success")
            self.start_btn.clicked.connect(self._start)
            btn_layout.addWidget(self.start_btn)
            self.stop_btn = QPushButton("STOP")
            self.stop_btn.setObjectName("danger")
            self.stop_btn.clicked.connect(self._stop)
            self.stop_btn.setEnabled(False)
            btn_layout.addWidget(self.stop_btn)
            layout.addLayout(btn_layout)
            layout.addStretch()

        def _update_status(self, data):
            active = data.get("active", False)
            self.status_label.setText("RUNNING" if active else "STOPPED")
            self.status_label.setObjectName("status-on" if active else "status-off")
            self.status_label.setStyleSheet("")
            self.start_btn.setEnabled(not active)
            self.stop_btn.setEnabled(active)
            self.mode_label.setText(data.get("mode", "-"))
            self.profile_label.setText(data.get("profile", "default"))
            self.targets_label.setText(str(data.get("targets", 0)))
            self.radius_label.setText(str(data.get("in_radius", 0)))
            self.picked_label.setText(str(data.get("picked", 0)))
            self.cat_label.setText(data.get("active_cat", "all"))
            self.session_label.setText(data.get("session_stats", "-"))
            hp = data.get("hp")
            self.hp_label.setText(f"{hp}%" if hp is not None else "-")

        def _start(self):
            if not self.bot.running:
                pm = ProfileManager()
                current = pm.current()
                cfg = pm.load(current)
                self.bot.start(cfg, profile_name=current)
                if self._main_window:
                    self._main_window.start_overlay()

        def _stop(self):
            if self.bot.running:
                self.bot.stop()
                if self._main_window:
                    self._main_window.stop_overlay()


    class ProfilesTab(QWidget):
        def __init__(self):
            super().__init__()
            self._setup_ui()
            self._refresh()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            header = QLabel("Profiles")
            header.setObjectName("header")
            layout.addWidget(header)
            self.table = QTableWidget()
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Name", "Mode", "Radius"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(self.table)
            btn_layout = QHBoxLayout()
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(self._refresh)
            btn_layout.addWidget(refresh_btn)
            layout.addLayout(btn_layout)

        def _refresh(self):
            pm = ProfileManager()
            self.table.setRowCount(len(pm.names))
            for i, name in enumerate(pm.names):
                cfg = pm.load(name)
                loot = cfg.get("loot", {})
                self.table.setItem(i, 0, QTableWidgetItem(name))
                self.table.setItem(i, 1, QTableWidgetItem(loot.get("mode", "-")))
                self.table.setItem(i, 2, QTableWidgetItem(str(loot.get("pickup_radius_px", "-"))))


    class SettingsTab(QWidget):
        def __init__(self):
            super().__init__()
            self._values = {}
            self._setup_ui()
            self._load_values()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            header = QLabel("Settings")
            header.setObjectName("header")
            layout.addWidget(header)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { background: #16213e; }")
            container = QWidget()
            container.setStyleSheet("QWidget { background: #16213e; }")
            form = QFormLayout(container)
            self._add_spin(form, "Target FPS", "capture.target_fps", 30, 1, 120)
            self._add_check(form, "Double Buffer", "capture.double_buffer", True)
            self._add_spin(form, "Min Blob Area", "vision.min_blob_area", 120, 1, 5000)
            self._add_spin(form, "Hue Tolerance", "vision.hue_tolerance", 8, 1, 50)
            self._add_spin(form, "Sat Min", "vision.sat_min", 120, 0, 255)
            self._add_spin(form, "Val Min", "vision.val_min", 120, 0, 255)
            self._add_spin(form, "Radius Px", "loot.pickup_radius_px", 250, 50, 2000)
            self._add_spin(form, "Cooldown Ms", "loot.click_cooldown_ms", 300, 10, 2000)
            self._add_combo(form, "Mode", "loot.mode", "toggle", ["hold", "toggle", "single", "lazy"])
            self._add_check(form, "HP Flask", "hp_flask.enabled", True)
            self._add_entry(form, "HP Key", "hp_flask.key", "1")
            self._add_spin(form, "HP Threshold", "hp_flask.threshold", 0.65, 0.1, 1.0, 0.05)
            self._add_check(form, "Overlay", "overlay.enabled", True)
            scroll.setWidget(container)
            layout.addWidget(scroll)
            btn_layout = QHBoxLayout()
            save_btn = QPushButton("Apply")
            save_btn.setObjectName("success")
            save_btn.clicked.connect(self._apply)
            btn_layout.addWidget(save_btn)
            layout.addLayout(btn_layout)

        def _make_label(self, text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #ffffff; font-weight: bold; background: #16213e; padding: 4px;")
            return lbl

        def _add_spin(self, form, label, key, default, from_, to_, step=1):
            var = QSpinBox() if step == 1 else QDoubleSpinBox()
            var.setRange(from_, to_)
            var.setValue(default)
            if step != 1:
                var.setSingleStep(step)
            form.addRow(self._make_label(label), var)
            self._values[key] = var

        def _add_check(self, form, label, key, default):
            var = QCheckBox()
            var.setChecked(default)
            form.addRow(self._make_label(label), var)
            self._values[key] = var

        def _add_entry(self, form, label, key, default):
            var = QLineEdit(default)
            form.addRow(self._make_label(label), var)
            self._values[key] = var

        def _add_combo(self, form, label, key, default, options):
            var = QComboBox()
            var.addItems(options)
            var.setCurrentText(default)
            form.addRow(self._make_label(label), var)
            self._values[key] = var

        def _load_values(self):
            try:
                cfg = load_config(None)
                for key, widget in self._values.items():
                    parts = key.split(".")
                    val = cfg
                    for p in parts:
                        val = val.get(p, {}) if isinstance(val, dict) else None
                    if val is None:
                        continue
                    if isinstance(widget, QSpinBox):
                        widget.setValue(int(val))
                    elif isinstance(widget, QDoubleSpinBox):
                        widget.setValue(float(val))
                    elif isinstance(widget, QCheckBox):
                        widget.setChecked(bool(val))
                    elif isinstance(widget, QLineEdit):
                        widget.setText(str(val))
                    elif isinstance(widget, QComboBox):
                        widget.setCurrentText(str(val))
            except Exception:
                pass

        def _apply(self):
            QMessageBox.information(self, "OK", "Settings applied.")


    class StatsTab(QWidget):
        def __init__(self, signals):
            super().__init__()
            self.signals = signals
            self._setup_ui()
            self.signals.status_update.connect(self._update)

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            header = QLabel("Statistics")
            header.setObjectName("header")
            layout.addWidget(header)
            self.total_label = QLabel("0")
            self.ppm_label = QLabel("0")
            stats_group = QGroupBox("Session")
            stats_layout = QFormLayout()
            stats_layout.addRow("Total:", self.total_label)
            stats_layout.addRow("Per min:", self.ppm_label)
            stats_group.setLayout(stats_layout)
            layout.addWidget(stats_group)
            self.table = QTableWidget()
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Category", "Count", "%"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(self.table)

        def _update(self, data):
            stats = data.get("stats", {})
            total = data.get("picked", 0)
            self.total_label.setText(str(total))
            session = data.get("session_stats", "")
            if "(" in session:
                self.ppm_label.setText(session.split("(")[1].rstrip(")"))
            self.table.setRowCount(len(stats))
            for i, (cat, count) in enumerate(sorted(stats.items(), key=lambda x: -x[1])):
                self.table.setItem(i, 0, QTableWidgetItem(cat))
                self.table.setItem(i, 1, QTableWidgetItem(str(count)))
                pct = count / total * 100 if total else 0
                self.table.setItem(i, 2, QTableWidgetItem(f"{pct:.0f}%"))


    class LogsTab(QWidget):
        def __init__(self, signals):
            super().__init__()
            self.signals = signals
            self._setup_ui()
            self.signals.log_message.connect(self._append)

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            header = QLabel("Logs")
            header.setObjectName("header")
            layout.addWidget(header)
            self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setFont(QFont("Consolas", 10))
            layout.addWidget(self.log_text)
            btn_layout = QHBoxLayout()
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda: self.log_text.clear())
            btn_layout.addWidget(clear_btn)
            layout.addLayout(btn_layout)

        def _append(self, msg):
            self.log_text.append(msg)


    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Auto Loot PoE2 Helper")
            self.setMinimumSize(900, 650)
            self.signals = Signals()
            self.bot = BotRunner()
            self._overlay = None
            self._overlay_thread = None
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            tabs = QTabWidget()
            tabs.addTab(DashboardTab(self.signals, self.bot), "Dashboard")
            tabs.addTab(ProfilesTab(), "Profiles")
            tabs.addTab(SettingsTab(), "Settings")
            tabs.addTab(StatsTab(self.signals), "Stats")
            tabs.addTab(LogsTab(self.signals), "Logs")
            layout.addWidget(tabs)
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll)
            self._poll_timer.start(500)

        def _poll(self):
            if self.bot.running:
                self.signals.status_update.emit(self.bot.get_status())
                if self._overlay and not self.bot._stop_event.is_set():
                    pass

        def start_overlay(self):
            from .radius_overlay import RadiusOverlay, HAS_TK
            if HAS_TK and self._overlay is None:
                self._overlay = RadiusOverlay(self.bot._stop_event, self.bot.get_overlay_state)
                self._overlay_thread = threading.Thread(target=self._overlay.run, daemon=True)
                self._overlay_thread.start()

        def stop_overlay(self):
            if self._overlay:
                self._overlay.stop()
                self._overlay = None
                self._overlay_thread = None

        def closeEvent(self, event):
            if self.bot.running:
                self.bot.stop()
            self.stop_overlay()
            event.accept()


def run_gui():
    if not HAS_PYQT5:
        print("PyQt5 not installed. pip install PyQt5")
        return
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    for i in range(window.centralWidget().findChild(QTabWidget).count()):
        tab = window.centralWidget().findChild(QTabWidget).widget(i)
        if isinstance(tab, DashboardTab):
            tab.set_main_window(window)
            break
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()
