"""
桌面番茄钟 (Pomodoro Timer)
A desktop Pomodoro timer application built with tkinter.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
from datetime import datetime
import platform

# Try to import plyer for notifications (fallback to tkinter messagebox)
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_config.json")

DEFAULT_CONFIG = {
    "work_time": 25 * 60,       # 25 minutes
    "short_break": 5 * 60,      # 5 minutes
    "long_break": 15 * 60,      # 15 minutes
    "long_break_interval": 4,   # every 4 pomodoros
    "always_on_top": True,
    "theme": "tomato",
}


THEMES = {
    "tomato": {
        "bg": "#2b2b2b",
        "fg": "#ffffff",
        "accent": "#ff6347",
        "accent_light": "#ff8c7a",
        "card": "#363636",
        "card_border": "#444444",
        "timer_color": "#ff6347",
        "btn_bg": "#ff6347",
        "btn_fg": "#ffffff",
        "btn_hover": "#e5553a",
    },
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "accent": "#89b4fa",
        "accent_light": "#b4d0fb",
        "card": "#313244",
        "card_border": "#45475a",
        "timer_color": "#89b4fa",
        "btn_bg": "#89b4fa",
        "btn_fg": "#1e1e2e",
        "btn_hover": "#74c7ec",
    },
    "green": {
        "bg": "#1a1a2e",
        "fg": "#e0e0e0",
        "accent": "#4ecca3",
        "accent_light": "#7edfc0",
        "card": "#16213e",
        "card_border": "#0f3460",
        "timer_color": "#4ecca3",
        "btn_bg": "#4ecca3",
        "btn_fg": "#1a1a2e",
        "btn_hover": "#3db88b",
    },
}


class PomodoroTimer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("番茄钟")
        self.root.minsize(360, 500)

        self.config = self.load_config()
        self.theme = THEMES.get(self.config["theme"], THEMES["tomato"])

        # Timer state
        self.state = "idle"  # idle, work, short_break, long_break
        self.time_remaining = self.config["work_time"]
        self.is_running = False
        self.is_paused = False
        self.pomodoro_count = 0
        self.daily_count = 0
        self.total_focus_seconds = 0
        self.session_start = None

        # Load daily stats
        self.load_stats()

        self.setup_window()
        self.setup_ui()
        self.setup_menu()
        self.apply_theme()
        self.update_display()
        self.center_window()

        # Keyboard shortcuts
        self.root.bind("<space>", lambda e: self.toggle_timer())
        self.root.bind("<Escape>", lambda e: self.reset_timer())
        self.root.bind("<Control-n>", lambda e: self.open_settings())

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(saved)
                    return merged
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def load_stats(self):
        stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_stats.json")
        if os.path.exists(stats_file):
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                today = datetime.now().strftime("%Y-%m-%d")
                if stats.get("date") == today:
                    self.daily_count = stats.get("count", 0)
                    self.total_focus_seconds = stats.get("total_seconds", 0)
            except Exception:
                pass

    def save_stats(self):
        stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pomodoro_stats.json")
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump({
                    "date": today,
                    "count": self.daily_count,
                    "total_seconds": self.total_focus_seconds,
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def setup_window(self):
        if self.config["always_on_top"]:
            self.root.attributes("-topmost", True)
        self.root.configure(bg=self.theme["bg"])

    def setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container
        self.main_frame = tk.Frame(self.root, bg=self.theme["bg"])
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.main_frame.columnconfigure(0, weight=1)

        # Status label
        self.status_label = tk.Label(
            self.main_frame,
            text="准备开始",
            font=("Segoe UI", 14),
            bg=self.theme["bg"],
            fg=self.theme["accent_light"],
        )
        self.status_label.grid(row=0, column=0, pady=(0, 5))

        # Timer display
        self.timer_label = tk.Label(
            self.main_frame,
            text="25:00",
            font=("Segoe UI", 72, "bold"),
            bg=self.theme["bg"],
            fg=self.theme["timer_color"],
        )
        self.timer_label.grid(row=1, column=0, pady=5)

        # Progress bar (circular-like via canvas, but we use a simple determinate bar)
        self.progress = ttk.Progressbar(
            self.main_frame,
            mode="determinate",
            length=280,
        )
        self.progress.grid(row=2, column=0, pady=(10, 0))

        self.percent_label = tk.Label(
            self.main_frame,
            text="0%",
            font=("Segoe UI", 10),
            bg=self.theme["bg"],
            fg=self.theme["accent_light"],
        )
        self.percent_label.grid(row=3, column=0, pady=(2, 5))

        # Button frame
        self.btn_frame = tk.Frame(self.main_frame, bg=self.theme["bg"])
        self.btn_frame.grid(row=4, column=0, pady=15)

        self.start_btn = self.create_button(self.btn_frame, "开始", self.toggle_timer, 0)
        self.reset_btn = self.create_button(self.btn_frame, "重置", self.reset_timer, 1)

        self.skip_btn = tk.Button(
            self.main_frame,
            text="跳过当前阶段 ▶▶",
            font=("Segoe UI", 10),
            bg=self.theme["card"],
            fg=self.theme["accent_light"],
            activebackground=self.theme["card_border"],
            activeforeground=self.theme["fg"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.skip_phase,
        )
        self.skip_btn.grid(row=5, column=0, pady=(0, 15))

        # Stats display
        self.stats_frame = tk.Frame(self.main_frame, bg=self.theme["card"], highlightbackground=self.theme["card_border"], highlightthickness=1)
        self.stats_frame.grid(row=6, column=0, sticky="ew", pady=5)
        self.stats_frame.columnconfigure((0, 1, 2), weight=1)

        self.pomodoro_count_label = tk.Label(
            self.stats_frame,
            text=f"🍅 今日\n{self.daily_count}",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["card"],
            fg=self.theme["fg"],
            justify="center",
        )
        self.pomodoro_count_label.grid(row=0, column=0, padx=5, pady=8)

        self.focus_time_label = tk.Label(
            self.stats_frame,
            text="⏱ 专注\n0h 0m",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["card"],
            fg=self.theme["fg"],
            justify="center",
        )
        self.focus_time_label.grid(row=0, column=1, padx=5, pady=8)

        self.session_label = tk.Label(
            self.stats_frame,
            text="🔄 本轮\n0",
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["card"],
            fg=self.theme["fg"],
            justify="center",
        )
        self.session_label.grid(row=0, column=2, padx=5, pady=8)

        self.update_stats_display()

    def create_button(self, parent, text, command, col):
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 12, "bold"),
            bg=self.theme["btn_bg"],
            fg=self.theme["btn_fg"],
            activebackground=self.theme["btn_hover"],
            activeforeground=self.theme["btn_fg"],
            relief="flat",
            bd=0,
            padx=25,
            pady=8,
            cursor="hand2",
            command=command,
        )
        btn.grid(row=0, column=col, padx=6)
        return btn

    def setup_menu(self):
        menubar = tk.Menu(self.root, bg=self.theme["card"], fg=self.theme["fg"],
                          activebackground=self.theme["accent"], activeforeground=self.theme["btn_fg"])
        self.root.config(menu=menubar)

        options_menu = tk.Menu(menubar, tearoff=0, bg=self.theme["card"], fg=self.theme["fg"],
                               activebackground=self.theme["accent"], activeforeground=self.theme["btn_fg"])
        options_menu.add_command(label="设置 (Ctrl+N)", command=self.open_settings)
        options_menu.add_separator()
        options_menu.add_command(label="重置统计数据", command=self.reset_stats)
        options_menu.add_separator()
        options_menu.add_command(label="退出", command=self.on_close)
        menubar.add_cascade(label="选项", menu=options_menu)

        theme_menu = tk.Menu(menubar, tearoff=0, bg=self.theme["card"], fg=self.theme["fg"],
                             activebackground=self.theme["accent"], activeforeground=self.theme["btn_fg"])
        for name in THEMES:
            theme_menu.add_command(label=name.capitalize(), command=lambda n=name: self.set_theme(n))
        menubar.add_cascade(label="主题", menu=theme_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=self.theme["card"], fg=self.theme["fg"],
                            activebackground=self.theme["accent"], activeforeground=self.theme["btn_fg"])
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

    def apply_theme(self):
        self.root.configure(bg=self.theme["bg"])
        self.main_frame.configure(bg=self.theme["bg"])
        self.status_label.configure(bg=self.theme["bg"], fg=self.theme["accent_light"])
        self.timer_label.configure(bg=self.theme["bg"], fg=self.theme["timer_color"])
        self.percent_label.configure(bg=self.theme["bg"], fg=self.theme["accent_light"])
        self.btn_frame.configure(bg=self.theme["bg"])
        self.stats_frame.configure(bg=self.theme["card"], highlightbackground=self.theme["card_border"])
        self.skip_btn.configure(bg=self.theme["card"], fg=self.theme["accent_light"],
                                 activebackground=self.theme["card_border"], activeforeground=self.theme["fg"])
        for child in self.stats_frame.winfo_children():
            child.configure(bg=self.theme["card"], fg=self.theme["fg"])
        for btn in [self.start_btn, self.reset_btn]:
            btn.configure(bg=self.theme["btn_bg"], fg=self.theme["btn_fg"],
                          activebackground=self.theme["btn_hover"], activeforeground=self.theme["btn_fg"])

        # Style the progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Horizontal.TProgressbar",
            background=self.theme["timer_color"],
            troughcolor=self.theme["card"],
            bordercolor=self.theme["card_border"],
            lightcolor=self.theme["timer_color"],
            darkcolor=self.theme["timer_color"],
        )

    def set_theme(self, name):
        self.config["theme"] = name
        self.theme = THEMES[name]
        self.apply_theme()
        self.save_config()

    # ── Timer Logic ──────────────────────────────────────────

    def toggle_timer(self):
        if not self.is_running:
            if self.state == "idle":
                self.start_work()
            self.start_timer()
        else:
            self.pause_timer()

    def start_work(self):
        self.state = "work"
        self.time_remaining = self.config["work_time"]
        self.status_label.configure(text="🍅 专注中...")
        self.timer_label.configure(fg=self.theme["timer_color"])

    def start_timer(self):
        self.is_running = True
        self.is_paused = False
        self.start_btn.configure(text="暂停")
        self.session_start = time.time()
        self.update_timer()

    def pause_timer(self):
        self.is_running = False
        self.is_paused = True
        self.start_btn.configure(text="继续")
        if self.session_start:
            elapsed = time.time() - self.session_start
            self.total_focus_seconds += elapsed
            self.session_start = None

    def stop_timer(self):
        self.is_running = False
        self.is_paused = False
        self.start_btn.configure(text="开始")

    def reset_timer(self):
        self.stop_timer()
        self.state = "idle"
        self.time_remaining = self.config["work_time"]
        self.status_label.configure(text="准备开始")
        self.update_display()
        self.progress["value"] = 0

    def skip_phase(self):
        if self.is_running or self.is_paused:
            self.stop_timer()
            self.handle_timer_complete()

    def update_timer(self):
        if not self.is_running:
            return

        now = time.time()
        if self.session_start:
            elapsed = now - self.session_start
            self.time_remaining -= elapsed
        self.session_start = now

        if self.time_remaining <= 0:
            self.time_remaining = 0
            self.update_display()
            self.stop_timer()
            self.handle_timer_complete()
            return

        self.update_display()
        self.root.after(200, self.update_timer)

    def update_display(self):
        minutes = int(self.time_remaining // 60)
        seconds = int(self.time_remaining % 60)
        self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")

        total = self.config["work_time"]
        if self.state == "short_break":
            total = self.config["short_break"]
        elif self.state == "long_break":
            total = self.config["long_break"]
        if total > 0:
            pct = int((1 - self.time_remaining / total) * 100)
            self.progress["value"] = pct
            self.percent_label.configure(text=f"{pct}%")

    def handle_timer_complete(self):
        if self.state == "work":
            self.pomodoro_count += 1
            self.daily_count += 1
            if self.session_start:
                self.total_focus_seconds += time.time() - self.session_start
                self.session_start = None
            self.save_stats()
            self.update_stats_display()
            self.show_notification("番茄钟", "🎉 专注时间到！该休息一下了。")

            if self.pomodoro_count % self.config["long_break_interval"] == 0:
                self.start_long_break()
            else:
                self.start_short_break()

        elif self.state in ("short_break", "long_break"):
            self.state = "idle"
            self.status_label.configure(text="准备开始")
            self.show_notification("番茄钟", "休息结束！准备开始新的专注。")
            self.reset_timer()

    def start_short_break(self):
        self.state = "short_break"
        self.time_remaining = self.config["short_break"]
        self.status_label.configure(text="☕ 短休息")
        self.timer_label.configure(fg=self.theme["accent_light"])
        self.start_timer()

    def start_long_break(self):
        self.state = "long_break"
        self.time_remaining = self.config["long_break"]
        self.status_label.configure(text="🎉 长休息")
        self.timer_label.configure(fg=self.theme["accent"])
        self.start_timer()

    def show_notification(self, title, message):
        def notify():
            if HAS_PLYER:
                try:
                    notification.notify(
                        title=title,
                        message=message,
                        timeout=5,
                    )
                    return
                except Exception:
                    pass
            # Fallback: flash the window
            self.root.attributes("-topmost", False)
            self.root.attributes("-topmost", True)
            self.root.deiconify()
            self.root.lift()

        threading.Thread(target=notify, daemon=True).start()
        # Beep
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            print("\a")

    # ── Stats ────────────────────────────────────────────────

    def update_stats_display(self):
        self.pomodoro_count_label.configure(text=f"🍅 今日\n{self.daily_count}")
        hours = int(self.total_focus_seconds // 3600)
        minutes = int((self.total_focus_seconds % 3600) // 60)
        self.focus_time_label.configure(text=f"⏱ 专注\n{hours}h {minutes}m")
        self.session_label.configure(text=f"🔄 本轮\n{self.pomodoro_count}")

    def reset_stats(self):
        if messagebox.askyesno("重置统计", "确定要重置今日统计数据吗？"):
            self.daily_count = 0
            self.total_focus_seconds = 0
            self.pomodoro_count = 0
            self.save_stats()
            self.update_stats_display()

    # ── Settings ─────────────────────────────────────────────

    def open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("设置")
        dialog.configure(bg=self.theme["bg"])
        dialog.resizable(False, False)

        frame = tk.Frame(dialog, bg=self.theme["bg"], padx=20, pady=20)
        frame.pack()

        settings = [
            ("work_time", "专注时间 (分钟)", DEFAULT_CONFIG["work_time"] // 60),
            ("short_break", "短休息 (分钟)", DEFAULT_CONFIG["short_break"] // 60),
            ("long_break", "长休息 (分钟)", DEFAULT_CONFIG["long_break"] // 60),
            ("long_break_interval", "长休息间隔 (个)", DEFAULT_CONFIG["long_break_interval"]),
        ]

        entries = {}
        for i, (key, label, default) in enumerate(settings):
            tk.Label(frame, text=label, font=("Segoe UI", 11),
                     bg=self.theme["bg"], fg=self.theme["fg"]).grid(row=i, column=0, sticky="w", pady=6)
            var = tk.StringVar(value=str(self.config.get(key, default)))
            entry = tk.Entry(frame, textvariable=var, font=("Segoe UI", 11),
                             width=8, justify="center",
                             bg=self.theme["card"], fg=self.theme["fg"],
                             relief="flat", bd=0)
            entry.grid(row=i, column=1, padx=(10, 0), pady=6)
            entries[key] = var

        # Always on top checkbox
        var_top = tk.BooleanVar(value=self.config["always_on_top"])
        cb = tk.Checkbutton(
            frame, text="窗口置顶", variable=var_top,
            font=("Segoe UI", 11),
            bg=self.theme["bg"], fg=self.theme["fg"],
            activebackground=self.theme["bg"],
            activeforeground=self.theme["fg"],
            selectcolor=self.theme["card"],
        )
        cb.grid(row=len(settings), column=0, columnspan=2, sticky="w", pady=10)

        def save():
            try:
                for key, var in entries.items():
                    val = int(var.get().strip())
                    if key == "long_break_interval":
                        val = max(1, val)
                    else:
                        val = max(1, min(999, val))
                        if key in ("work_time", "short_break", "long_break"):
                            val *= 60  # convert to seconds
                    self.config[key] = val

                self.config["always_on_top"] = var_top.get()
                self.root.attributes("-topmost", self.config["always_on_top"])
                self.save_config()

                if self.state == "idle":
                    self.time_remaining = self.config["work_time"]
                    self.update_display()

                dialog.destroy()
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字", parent=dialog)

        btn_frame = tk.Frame(frame, bg=self.theme["bg"])
        btn_frame.grid(row=len(settings) + 1, column=0, columnspan=2, pady=(15, 0))

        tk.Button(
            btn_frame, text="保存", font=("Segoe UI", 11, "bold"),
            bg=self.theme["btn_bg"], fg=self.theme["btn_fg"],
            activebackground=self.theme["btn_hover"],
            activeforeground=self.theme["btn_fg"],
            relief="flat", bd=0, padx=20, pady=4, cursor="hand2",
            command=save,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame, text="取消", font=("Segoe UI", 11),
            bg=self.theme["card"], fg=self.theme["fg"],
            activebackground=self.theme["card_border"],
            activeforeground=self.theme["fg"],
            relief="flat", bd=0, padx=20, pady=4, cursor="hand2",
            command=dialog.destroy,
        ).pack(side="left", padx=5)

        # Position relative to main window
        dialog.transient(self.root)
        dialog.grab_set()
        self.center_dialog(dialog)

    # ── Utility ──────────────────────────────────────────────

    def center_window(self):
        self.root.update_idletasks()
        w, h = 400, 520
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def center_dialog(self, dialog):
        dialog.update_idletasks()
        dw, dh = 300, 300
        px = self.root.winfo_x() + (self.root.winfo_width() - dw) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{px}+{py}")

    def show_about(self):
        messagebox.showinfo(
            "关于 番茄钟",
            "桌面番茄钟 v1.0\n\n"
            "基于 Pomodoro Technique®\n"
            "专注25分钟 → 休息5分钟\n\n"
            "快捷键:\n"
            "  空格  - 开始/暂停\n"
            "  Esc   - 重置\n"
            "  Ctrl+N - 设置"
        )

    def on_close(self):
        if self.is_running:
            if not messagebox.askyesno("退出", "计时器正在运行，确定要退出吗？"):
                return
        self.save_stats()
        self.save_config()
        self.root.destroy()


if __name__ == "__main__":
    PomodoroTimer()
