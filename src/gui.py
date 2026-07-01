from __future__ import annotations
import time
from typing import Any, Optional, Union
import customtkinter as ctk
from src.config_manager import state_lock, DEFAULT_CONFIG, save_config
from src.osc_handler import OSCMessageHandler

class OSCProxyGUI(ctk.CTk):
    handler: OSCMessageHandler
    config: dict[str, Any]
    last_sleeping_state: bool
    sliders: dict[str, tuple[ctk.CTkSlider, ctk.CTkLabel]]

    def __init__(self, handler: OSCMessageHandler, config: dict[str, Any]) -> None:
        super().__init__()
        self.handler = handler
        self.config = config
        self.title("OSC Proxy Configuration")
        self.geometry("800x550")
        self.resizable(False, False)

        # set grid layout 1x2
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1) # Spacer

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="OSC Proxy", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.status_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#388E3C", height=35)
        self.status_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.status_frame.pack_propagate(False)
        self.status_label = ctk.CTkLabel(self.status_frame, text="STATUS: ACTIVE", font=("Arial", 14, "bold"), text_color="white")
        self.status_label.pack(expand=True)

        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.show_dashboard, fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w")
        self.btn_dashboard.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_routing = ctk.CTkButton(self.sidebar_frame, text="Routing & Mix", command=self.show_routing, fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w")
        self.btn_routing.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        self.btn_advanced = ctk.CTkButton(self.sidebar_frame, text="Advanced", command=self.show_advanced, fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w")
        self.btn_advanced.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.btn_logs = ctk.CTkButton(self.sidebar_frame, text="Event Logs", command=self.show_logs, fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w")
        self.btn_logs.grid(row=5, column=0, padx=20, pady=5, sticky="ew")

        self.btn_save = ctk.CTkButton(self.sidebar_frame, text="Save Config", command=self.do_save, fg_color="#1f538d", font=("Arial", 14, "bold"), height=40)
        self.btn_save.grid(row=7, column=0, padx=20, pady=20, sticky="ew")

        # --- Main Frames ---
        self.dashboard_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.routing_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.advanced_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.logs_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        self.sliders = {}
        
        self.setup_dashboard()
        self.setup_routing()
        self.setup_advanced()
        self.setup_logs()

        self.last_sleeping_state = False
        self.show_dashboard()
        self.update_status()
        
        self.bind("<<SteamVRClosed>>", self._on_steamvr_closed)

    # View Setup Methods
    def setup_dashboard(self) -> None:
        self.dashboard_frame.grid_rowconfigure(0, weight=1)
        self.dashboard_frame.grid_rowconfigure(1, weight=1)
        self.dashboard_frame.grid_columnconfigure(0, weight=1)
        self.dashboard_frame.grid_columnconfigure(1, weight=1)

        # Graph section
        graph_card = ctk.CTkFrame(self.dashboard_frame)
        graph_card.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="nsew")
        ctk.CTkLabel(graph_card, text="Throughput", font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        
        self.throughput_history = [0] * 35
        self.graph_canvas = ctk.CTkCanvas(graph_card, height=140, bg="#2b2b2b", highlightthickness=0)
        self.graph_canvas.pack(fill="both", expand=True, padx=15, pady=10)

        # Forwarding Toggles
        fwd_card = ctk.CTkFrame(self.dashboard_frame)
        fwd_card.grid(row=1, column=0, padx=(20, 10), pady=(10, 20), sticky="nsew")
        ctk.CTkLabel(fwd_card, text="Forwarding", font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=(10, 15))
        
        self.fwd_mouth = ctk.BooleanVar(value=self.config["forwarding"]["enable_mouth"])
        self.fwd_right = ctk.BooleanVar(value=self.config["forwarding"]["enable_right_eye"])
        self.fwd_left = ctk.BooleanVar(value=self.config["forwarding"]["enable_left_eye"])

        ctk.CTkSwitch(fwd_card, text="Mouth Parameters", variable=self.fwd_mouth, command=self.on_forwarding_change).pack(anchor="w", padx=20, pady=10)
        ctk.CTkSwitch(fwd_card, text="Right Eye Parameters", variable=self.fwd_right, command=self.on_forwarding_change).pack(anchor="w", padx=20, pady=10)
        ctk.CTkSwitch(fwd_card, text="Left Eye Parameters", variable=self.fwd_left, command=self.on_forwarding_change).pack(anchor="w", padx=20, pady=10)

        # Calibration
        calib_card = ctk.CTkFrame(self.dashboard_frame)
        calib_card.grid(row=1, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew")
        ctk.CTkLabel(calib_card, text="Calibration", font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=(10, 15))
        
        self.calib_btn = ctk.CTkButton(calib_card, text="Calibrate Center", font=("Arial", 14), height=40, command=self.start_calibration)
        self.calib_btn.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(calib_card, text="Reset Calibration", width=120, height=30, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self.reset_calibration).pack(pady=10)

    def setup_routing(self) -> None:
        self.create_mix_section(self.routing_frame, "Eyelid Mix", "eyelid")
        self.create_mix_section(self.routing_frame, "Gaze Mix (X/Y Combined)", "gaze")

    def setup_advanced(self) -> None:
        self.create_sleep_section(self.advanced_frame)
        self.create_steamvr_section(self.advanced_frame)

    def setup_logs(self) -> None:
        ctk.CTkLabel(self.logs_frame, text="Event Logs", font=("Arial", 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        self.log_textbox = ctk.CTkTextbox(self.logs_frame, font=("Consolas", 12))
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_textbox.configure(state="disabled")

    # Layout Swapping
    def select_frame(self, name: str) -> None:
        self.btn_dashboard.configure(fg_color=("gray75", "gray25") if name == "dashboard" else "transparent")
        self.btn_routing.configure(fg_color=("gray75", "gray25") if name == "routing" else "transparent")
        self.btn_advanced.configure(fg_color=("gray75", "gray25") if name == "advanced" else "transparent")
        self.btn_logs.configure(fg_color=("gray75", "gray25") if name == "logs" else "transparent")

        self.dashboard_frame.grid_forget()
        self.routing_frame.grid_forget()
        self.advanced_frame.grid_forget()
        self.logs_frame.grid_forget()

        if name == "dashboard":
            self.dashboard_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "routing":
            self.routing_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "advanced":
            self.advanced_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "logs":
            self.logs_frame.grid(row=0, column=1, sticky="nsew")

    def show_dashboard(self) -> None: self.select_frame("dashboard")
    def show_routing(self) -> None: self.select_frame("routing")
    def show_advanced(self) -> None: self.select_frame("advanced")
    def show_logs(self) -> None: self.select_frame("logs")

    # Logging and Data Updates
    def do_save(self) -> None:
        save_config(self.config)
        self.log_message("設定を config.json に保存しました。")

    def _on_steamvr_closed(self, event: Any = None) -> None:
        self.log_message("SteamVRが終了しました。OSC Proxyを終了します...")
        self.after(1000, self.destroy)

    def log_message(self, msg: str) -> None:
        timestamp_str = time.strftime('%H:%M:%S')
        full_msg = f"[{timestamp_str}] {msg}\n"
        
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", full_msg)
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        
        import os, sys
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        date_str = time.strftime('%Y-%m-%d')
        log_path = os.path.join(base_dir, f"osc_proxy_{date_str}.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(full_msg)
        except Exception:
            pass

    def on_forwarding_change(self) -> None:
        with state_lock:
            self.config["forwarding"]["enable_mouth"] = self.fwd_mouth.get()
            self.config["forwarding"]["enable_right_eye"] = self.fwd_right.get()
            self.config["forwarding"]["enable_left_eye"] = self.fwd_left.get()

    def update_status(self) -> None:
        mps, is_sleeping = self.handler.get_status()
        self.draw_throughput_graph(mps)
        
        if is_sleeping:
            self.status_frame.configure(fg_color="#D32F2F") # Red
            self.status_label.configure(text="STATUS: SLEEPING")
        else:
            self.status_frame.configure(fg_color="#388E3C") # Green
            self.status_label.configure(text="STATUS: ACTIVE")
            
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
            width = 560
        height = self.graph_canvas.winfo_height()
        if height <= 1:
            height = 140
            
        # Grid lines
        for ratio in [0.25, 0.5, 0.75]:
            y = height * (1 - ratio)
            self.graph_canvas.create_line(0, y, width, y, fill="#3e3e3e", dash=(2, 2))
            
        # Coordinates
        max_val = max(100, max(self.throughput_history))
        points = []
        n_points = len(self.throughput_history)
        for i, val in enumerate(self.throughput_history):
            x = i * (width / max(1, n_points - 1))
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

    # Calibration Methods
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
        self.log_message(f"センターキャリブレーション完了: 右目({rx:.2f}, {ry:.2f}) 左目({lx:.2f}, {ly:.2f})")

    def reset_calibration(self) -> None:
        with state_lock:
            self.config["calibration"] = DEFAULT_CONFIG["calibration"].copy()
        self.log_message("キャリブレーション設定を初期値にリセットしました。")

    # Mix Sections
    def create_mix_section(self, parent: ctk.CTkFrame, title: str, config_key: str) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", padx=20, pady=(20, 0))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text=title, font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=lambda k=config_key: self.reset_mix(k)).pack(side="right")
        
        for side_out in ["right_out", "left_out"]:
            frame = ctk.CTkFrame(section, fg_color="gray25")
            frame.pack(fill="x", padx=10, pady=(5, 10))
            
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
        self.log_message(f"{config_key.capitalize()} Mix設定を初期値にリセットしました。")

    # Advanced Settings Sections
    def create_sleep_section(self, parent: ctk.CTkFrame) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", padx=20, pady=(20, 0))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Sleep Mode", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=self.reset_sleep).pack(side="right")
        
        self.sleep_enabled = ctk.BooleanVar(value=self.config["sleep_mode"]["enabled"])
        cb = ctk.CTkSwitch(section, text="Enable Sleep Mode", variable=self.sleep_enabled, command=self.on_sleep_change)
        cb.pack(anchor="w", padx=20, pady=10)
        
        self.sleep_mouth = ctk.BooleanVar(value=self.config["sleep_mode"]["enable_mouth"])
        cb_mouth = ctk.CTkSwitch(section, text="Forward Mouth Data (1 msg/s)", variable=self.sleep_mouth, command=self.on_sleep_change)
        cb_mouth.pack(anchor="w", padx=20, pady=(0, 10))
        
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
            self.config["sleep_mode"]["enable_mouth"] = self.sleep_mouth.get()
            try: self.config["sleep_mode"]["timeout_seconds"] = float(self.timeout_entry.get())
            except ValueError: pass
            try: self.config["sleep_mode"]["change_threshold"] = float(self.threshold_entry.get())
            except ValueError: pass
            try: self.config["sleep_mode"]["closed_value"] = float(self.closed_val_entry.get())
            except ValueError: pass

    def reset_sleep(self) -> None:
        default = DEFAULT_CONFIG["sleep_mode"]
        with state_lock:
            self.config["sleep_mode"] = default.copy()
        
        self.sleep_enabled.set(default["enabled"])
        self.sleep_mouth.set(default.get("enable_mouth", True))
        self.timeout_entry.delete(0, 'end')
        self.timeout_entry.insert(0, str(default["timeout_seconds"]))
        self.threshold_entry.delete(0, 'end')
        self.threshold_entry.insert(0, str(default["change_threshold"]))
        self.closed_val_entry.delete(0, 'end')
        self.closed_val_entry.insert(0, str(default["closed_value"]))
        self.log_message("スリープモード設定を初期値にリセットしました。")

    def create_steamvr_section(self, parent: ctk.CTkFrame) -> None:
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", padx=20, pady=(20, 20))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="SteamVR Settings", font=("Arial", 16, "bold")).pack(side="left")
        
        self.steamvr_enabled = ctk.BooleanVar(value=self.config["steamvr"]["auto_launch"])
        cb = ctk.CTkSwitch(section, text="SteamVR起動時に自動実行", variable=self.steamvr_enabled, command=self.on_steamvr_change)
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
                    self.log_message(f"SteamVRの自動起動設定を{status_str}しました。")
                openvr.shutdown()
            except Exception as e:
                self.log_message(f"自動起動設定の変更中にエラー: {e}")
