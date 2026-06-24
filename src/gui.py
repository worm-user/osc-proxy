from __future__ import annotations
import time
from typing import Any, Optional, Union
import customtkinter as ctk
from src.config_manager import state_lock, DEFAULT_CONFIG, save_config
from src.osc_handler import OSCMessageHandler

class DetailedSettingsWindow(ctk.CTkToplevel):
    parent: OSCProxyGUI
    config: dict[str, Any]
    sliders: dict[str, tuple[ctk.CTkSlider, ctk.CTkLabel]]
    sleep_enabled: ctk.BooleanVar
    timeout_entry: ctk.CTkEntry
    threshold_entry: ctk.CTkEntry
    closed_val_entry: ctk.CTkEntry
    steamvr_enabled: ctk.BooleanVar

    def __init__(self, parent: OSCProxyGUI, config: dict[str, Any]) -> None:
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.title("Detailed Settings")
        self.geometry("500x650")
        self.resizable(False, False)
        
        self.sliders = {}
        
        # Scrollable area for setting groups
        main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=(15, 5))
        
        self.create_mix_section(main_frame, "Eyelid Mix", "eyelid")
        self.create_mix_section(main_frame, "Gaze Mix (X/Y Combined)", "gaze")
        self.create_sleep_section(main_frame)
        self.create_steamvr_section(main_frame)
        
        # Save Button fixed at the bottom (outside scrollable frame)
        save_btn = ctk.CTkButton(self, text="設定をファイルに保存", font=("Arial", 15, "bold"), height=45, command=self.do_save)
        save_btn.pack(fill="x", padx=15, pady=(5, 15))
        
        self.after(10, self.lift_window)

    def lift_window(self) -> None:
        self.lift()
        self.focus()

    def do_save(self) -> None:
        save_config(self.config)
        self.parent.log_message("設定を config.json に保存しました。")

    def create_mix_section(self, parent: Union[ctk.CTkFrame, ctk.CTkScrollableFrame], title: str, config_key: str) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text=title, font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=lambda k=config_key: self.reset_mix(k)).pack(side="right")
        
        for side_out in ["right_out", "left_out"]:
            frame = ctk.CTkFrame(section, fg_color="gray25")
            frame.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(frame, text=f"Output: {side_out.replace('_', ' ').title()}", font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=2)
            
            for side_in in ["right_in", "left_in"]:
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=2)
                
                ctk.CTkLabel(row, text=f"From {side_in.replace('_', ' ').title()}:", width=120, anchor="e").pack(side="left", padx=5)
                
                slider = ctk.CTkSlider(row, from_=0.0, to=1.0, command=lambda v, k=config_key, o=side_out, i=side_in: self.on_mix_change(v, k, o, i))
                slider.set(self.config["mix"][config_key][side_out][side_in])
                slider.pack(side="left", fill="x", expand=True, padx=5)
                
                val_lbl = ctk.CTkLabel(row, text=f"{slider.get():.2f}", width=40)
                val_lbl.pack(side="left")
                
                self.sliders[f"{config_key}_{side_out}_{side_in}"] = (slider, val_lbl)

    def on_mix_change(self, value: float | str, config_key: str, side_out: str, side_in: str) -> None:
        val = float(value)
        with state_lock:
            self.config["mix"][config_key][side_out][side_in] = val
        slider, val_lbl = self.sliders[f"{config_key}_{side_out}_{side_in}"]
        val_lbl.configure(text=f"{val:.2f}")

    def reset_mix(self, config_key: str) -> None:
        default = DEFAULT_CONFIG["mix"][config_key]
        for side_out in ["right_out", "left_out"]:
            for side_in in ["right_in", "left_in"]:
                val = default[side_out][side_in]
                with state_lock:
                    self.config["mix"][config_key][side_out][side_in] = val
                slider, val_lbl = self.sliders[f"{config_key}_{side_out}_{side_in}"]
                slider.set(val)
                val_lbl.configure(text=f"{val:.2f}")
        self.parent.log_message(f"{config_key.capitalize()} Mix設定を初期値にリセットしました。")

    def create_sleep_section(self, parent: Union[ctk.CTkFrame, ctk.CTkScrollableFrame]) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Sleep Mode", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=self.reset_sleep).pack(side="right")
        
        self.sleep_enabled = ctk.BooleanVar(value=self.config["sleep_mode"]["enabled"])
        cb = ctk.CTkCheckBox(section, text="Enable Sleep Mode", variable=self.sleep_enabled, command=self.on_sleep_change)
        cb.pack(anchor="w", padx=20, pady=10)
        
        row1 = ctk.CTkFrame(section, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row1, text="Timeout (sec):", width=120, anchor="e").pack(side="left", padx=5)
        self.timeout_entry = ctk.CTkEntry(row1)
        self.timeout_entry.insert(0, str(self.config["sleep_mode"]["timeout_seconds"]))
        self.timeout_entry.pack(side="left", fill="x", expand=True)
        self.timeout_entry.bind("<KeyRelease>", self.on_sleep_change)
        
        row2 = ctk.CTkFrame(section, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row2, text="Change Threshold:", width=120, anchor="e").pack(side="left", padx=5)
        self.threshold_entry = ctk.CTkEntry(row2)
        self.threshold_entry.insert(0, str(self.config["sleep_mode"]["change_threshold"]))
        self.threshold_entry.pack(side="left", fill="x", expand=True)
        self.threshold_entry.bind("<KeyRelease>", self.on_sleep_change)

        row3 = ctk.CTkFrame(section, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row3, text="Closed Value:", width=120, anchor="e").pack(side="left", padx=5)
        self.closed_val_entry = ctk.CTkEntry(row3)
        self.closed_val_entry.insert(0, str(self.config["sleep_mode"]["closed_value"]))
        self.closed_val_entry.pack(side="left", fill="x", expand=True)
        self.closed_val_entry.bind("<KeyRelease>", self.on_sleep_change)

    def on_sleep_change(self, event: Any = None) -> None:
        with state_lock:
            self.config["sleep_mode"]["enabled"] = self.sleep_enabled.get()
            try: self.config["sleep_mode"]["timeout_seconds"] = float(self.timeout_entry.get())
            except: pass
            try: self.config["sleep_mode"]["change_threshold"] = float(self.threshold_entry.get())
            except: pass
            try: self.config["sleep_mode"]["closed_value"] = float(self.closed_val_entry.get())
            except: pass

    def reset_sleep(self) -> None:
        default = DEFAULT_CONFIG["sleep_mode"]
        with state_lock:
            self.config["sleep_mode"] = default.copy()
        
        self.sleep_enabled.set(default["enabled"])
        self.timeout_entry.delete(0, 'end')
        self.timeout_entry.insert(0, str(default["timeout_seconds"]))
        self.threshold_entry.delete(0, 'end')
        self.threshold_entry.insert(0, str(default["change_threshold"]))
        self.closed_val_entry.delete(0, 'end')
        self.closed_val_entry.insert(0, str(default["closed_value"]))
        self.parent.log_message("スリープモード設定を初期値にリセットしました。")

    def create_steamvr_section(self, parent: Union[ctk.CTkFrame, ctk.CTkScrollableFrame]) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="SteamVR Settings", font=("Arial", 16, "bold")).pack(side="left")
        
        self.steamvr_enabled = ctk.BooleanVar(value=self.config["steamvr"]["auto_launch"])
        cb = ctk.CTkCheckBox(section, text="SteamVR起動時に自動実行", variable=self.steamvr_enabled, command=self.on_steamvr_change)
        cb.pack(anchor="w", padx=20, pady=10)

    def on_steamvr_change(self) -> None:
        enabled = self.steamvr_enabled.get()
        with state_lock:
            self.config["steamvr"]["auto_launch"] = enabled
        
        from src.utils import is_steamvr_running
        if is_steamvr_running():
            try:
                import openvr
                openvr.init(openvr.VRApplication_Utility)
                apps = openvr.VRApplications()
                if apps.isApplicationInstalled("custom.osc.eyeproxy"):
                    apps.setApplicationAutoLaunch("custom.osc.eyeproxy", enabled)
                    status_str = "有効化" if enabled else "無効化"
                    self.parent.log_message(f"SteamVRの自動起動設定を{status_str}しました。")
                openvr.shutdown()
            except Exception as e:
                self.parent.log_message(f"自動起動設定の変更中にエラー: {e}")


class OSCProxyGUI(ctk.CTk):
    handler: OSCMessageHandler
    config: dict[str, Any]
    settings_window: Optional[DetailedSettingsWindow]
    banner_frame: ctk.CTkFrame
    banner_label: ctk.CTkLabel
    log_frame: ctk.CTkFrame
    log_textbox: ctk.CTkTextbox
    main_frame: ctk.CTkFrame
    calib_btn: ctk.CTkButton
    throughput_history: list[int]
    graph_canvas: ctk.CTkCanvas
    last_sleeping_state: bool

    def __init__(self, handler: OSCMessageHandler, config: dict[str, Any]) -> None:
        super().__init__()
        self.handler = handler
        self.config = config
        self.title("OSC Proxy Configuration")
        self.geometry("450x680")
        self.resizable(False, False)
        
        self.settings_window = None
        
        # Banner (top)
        self.banner_frame = ctk.CTkFrame(self, fg_color="#388E3C", height=45)
        self.banner_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.banner_frame.pack_propagate(False)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="STATUS: ACTIVE", font=("Arial", 20, "bold"), text_color="white")
        self.banner_label.pack(expand=True)
        
        # Event Log Frame (bottom)
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="x", side="bottom", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(self.log_frame, text="Event Log", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(2, 2))
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, height=300, font=("Consolas", 11))
        self.log_textbox.pack(fill="x", padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")
        
        # Main Layout (middle)
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.create_calibration_section(self.main_frame)
        self.create_buttons_section(self.main_frame)
        self.create_graph_section(self.main_frame)
        
        self.last_sleeping_state = False
        self.update_status()

    def log_message(self, msg: str) -> None:
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def open_detailed_settings(self) -> None:
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = DetailedSettingsWindow(self, self.config)
        else:
            self.settings_window.focus()
            self.settings_window.lift()

    def create_calibration_section(self, parent: ctk.CTkFrame) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Gaze Calibration", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=self.reset_calibration).pack(side="right")
        
        self.calib_btn = ctk.CTkButton(section, text="Calibrate Center", font=("Arial", 14), height=40, command=self.start_calibration)
        self.calib_btn.pack(fill="x", padx=20, pady=10)

    def start_calibration(self) -> None:
        self.calib_btn.configure(state="disabled")
        countdown = self.config.get("calibration", {}).get("countdown_seconds", 5)
        self.log_message(f"センターキャリブレーションを開始しました。{countdown}秒間正面を向いてください...")
        self.calib_countdown(countdown)

    def calib_countdown(self, seconds: int) -> None:
        if seconds > 0:
            self.calib_btn.configure(text=f"Look straight ahead... {seconds}")
            self.after(1000, self.calib_countdown, seconds - 1)
        else:
            self.calib_btn.configure(text="Capturing...")
            self.after(100, self.execute_calibration)

    def execute_calibration(self) -> None:
        rx, lx, ry, ly = self.handler.get_raw_gaze()
        with state_lock:
            self.config["calibration"]["right_gaze_x_offset"] = rx
            self.config["calibration"]["left_gaze_x_offset"] = lx
            self.config["calibration"]["right_gaze_y_offset"] = ry
            self.config["calibration"]["left_gaze_y_offset"] = ly
        self.calib_btn.configure(text="Calibrate Center", state="normal")
        self.log_message(f"センターキャリブレーション完了: 右目オフセット({rx:.2f}, {ry:.2f}) 左目オフセット({lx:.2f}, {ly:.2f}) を設定しました。")

    def reset_calibration(self) -> None:
        with state_lock:
            self.config["calibration"] = DEFAULT_CONFIG["calibration"].copy()
        self.log_message("キャリブレーション設定を初期値にリセットしました。")

    def create_buttons_section(self, parent: ctk.CTkFrame) -> None:
        settings_btn = ctk.CTkButton(parent, text="詳細設定を開く", font=("Arial", 14, "bold"), height=40, command=self.open_detailed_settings)
        settings_btn.pack(fill="x", pady=(0, 10))

    def create_graph_section(self, parent: ctk.CTkFrame) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        self.throughput_history = [0] * 20
        self.graph_canvas = ctk.CTkCanvas(section, height=75, bg="#2b2b2b", highlightthickness=0)
        self.graph_canvas.pack(fill="x", padx=10, pady=10)

    def update_status(self) -> None:
        mps, is_sleeping = self.handler.get_status()
        self.draw_throughput_graph(mps)
        
        if is_sleeping:
            self.banner_frame.configure(fg_color="#D32F2F") # Red
            self.banner_label.configure(text="STATUS: SLEEPING")
        else:
            self.banner_frame.configure(fg_color="#388E3C") # Green
            self.banner_label.configure(text="STATUS: ACTIVE")
            
        if is_sleeping != self.last_sleeping_state:
            self.last_sleeping_state = is_sleeping
            if is_sleeping:
                self.log_message("スリープ状態（SLEEPING）になりました。目を閉じた状態（Closed Value）に固定します。")
            else:
                self.log_message("アクティブ状態（ACTIVE）に戻りました。")
                
        self.after(500, self.update_status)

    def draw_throughput_graph(self, mps: int) -> None:
        self.throughput_history.append(mps)
        self.throughput_history.pop(0)
        
        self.graph_canvas.delete("all")
        
        width = self.graph_canvas.winfo_width()
        if width <= 1:
            width = 410  # Fit width for 450 window size
        height = 75
        
        # Grid lines (faint)
        for ratio in [0.25, 0.5, 0.75]:
            y = height * (1 - ratio)
            self.graph_canvas.create_line(0, y, width, y, fill="#3e3e3e", dash=(2, 2))
            
        # Coordinates
        max_val = max(100, max(self.throughput_history))
        points = []
        for i, val in enumerate(self.throughput_history):
            x = i * (width / 19)
            y = height - 5 - (val / max_val) * (height - 10)
            points.append((x, y))
            
        flat_points = []
        for p in points:
            flat_points.extend(p)
            
        # Draw area under the curve
        poly_points = [0, height] + flat_points + [width, height]
        self.graph_canvas.create_polygon(*poly_points, fill="#123c45", outline="", smooth=True)
        
        # Draw spline line
        self.graph_canvas.create_line(*flat_points, fill="#00B4D8", width=2, smooth=True)
        
        # Draw label overlay
        self.graph_canvas.create_text(10, 5, text=f"Throughput: {mps} msg/s", fill="#e0e0e0", font=("Arial", 11, "bold"), anchor="nw")
