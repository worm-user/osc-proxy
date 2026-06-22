import time
import customtkinter as ctk
from src.config_manager import state_lock, DEFAULT_CONFIG, save_config

class OSCProxyGUI(ctk.CTk):
    def __init__(self, handler, config):
        super().__init__()
        self.handler = handler
        self.config = config
        self.title("OSC Proxy Configuration")
        self.geometry("850x680")
        self.resizable(False, False)
        
        # Banner
        self.banner_frame = ctk.CTkFrame(self, fg_color="#388E3C", height=45)
        self.banner_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.banner_frame.pack_propagate(False)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="STATUS: ACTIVE", font=("Arial", 20, "bold"), text_color="white")
        self.banner_label.pack(expand=True)
        
        # Event Log Frame (bottom)
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="x", side="bottom", padx=10, pady=(5, 10))
        
        ctk.CTkLabel(self.log_frame, text="Event Log", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(2, 2))
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, height=100, font=("Consolas", 11))
        self.log_textbox.pack(fill="x", padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")
        
        # Main Layout (middle)
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Left Column (Mixes)
        self.left_col = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Right Column (Sleep, Calib, Save)
        self.right_col = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.right_col.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.sliders = {}
        
        self.create_mix_section(self.left_col, "Eyelid Mix", "eyelid")
        self.create_mix_section(self.left_col, "Gaze Mix (X/Y Combined)", "gaze")
        
        self.create_calibration_section(self.right_col)
        self.create_sleep_section(self.right_col)
        self.create_steamvr_section(self.right_col)
        
        # Status Label and Save Button
        bottom_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=10)
        
        self.status_label = ctk.CTkLabel(bottom_frame, text="Messages / sec: 0", font=("Arial", 12))
        self.status_label.pack(pady=5)
        
        save_btn = ctk.CTkButton(bottom_frame, text="Save Config to File", font=("Arial", 16, "bold"), height=45, command=self.do_save)
        save_btn.pack(fill="x")
        
        self.last_sleeping_state = False
        self.update_status()

    def do_save(self):
        save_config(self.config)
        self.log_message("設定を config.json に保存しました。")

    def log_message(self, msg):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def create_mix_section(self, parent, title, config_key):
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
                
                ctk.CTkLabel(row, text=f"From {side_in.replace('_', ' ').title()}:", width=100, anchor="e").pack(side="left", padx=5)
                
                slider = ctk.CTkSlider(row, from_=0.0, to=1.0, command=lambda v, k=config_key, o=side_out, i=side_in: self.on_mix_change(v, k, o, i))
                slider.set(self.config["mix"][config_key][side_out][side_in])
                slider.pack(side="left", fill="x", expand=True, padx=5)
                
                val_lbl = ctk.CTkLabel(row, text=f"{slider.get():.2f}", width=40)
                val_lbl.pack(side="left")
                
                self.sliders[f"{config_key}_{side_out}_{side_in}"] = (slider, val_lbl)

    def on_mix_change(self, value, config_key, side_out, side_in):
        val = float(value)
        with state_lock:
            self.config["mix"][config_key][side_out][side_in] = val
        slider, val_lbl = self.sliders[f"{config_key}_{side_out}_{side_in}"]
        val_lbl.configure(text=f"{val:.2f}")

    def reset_mix(self, config_key):
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

    def create_calibration_section(self, parent):
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Gaze Calibration", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=self.reset_calibration).pack(side="right")
        
        self.calib_btn = ctk.CTkButton(section, text="Calibrate Center", font=("Arial", 14), height=40, command=self.start_calibration)
        self.calib_btn.pack(fill="x", padx=20, pady=10)

    def start_calibration(self):
        self.calib_btn.configure(state="disabled")
        self.log_message("センターキャリブレーションを開始しました。3秒間正面を向いてください...")
        self.calib_countdown(3)

    def calib_countdown(self, seconds):
        if seconds > 0:
            self.calib_btn.configure(text=f"Look straight ahead... {seconds}")
            self.after(1000, self.calib_countdown, seconds - 1)
        else:
            self.calib_btn.configure(text="Capturing...")
            self.after(100, self.execute_calibration)

    def execute_calibration(self):
        rx, lx, ry, ly = self.handler.get_raw_gaze()
        with state_lock:
            self.config["calibration"]["right_gaze_x_offset"] = rx
            self.config["calibration"]["left_gaze_x_offset"] = lx
            self.config["calibration"]["right_gaze_y_offset"] = ry
            self.config["calibration"]["left_gaze_y_offset"] = ly
        self.calib_btn.configure(text="Calibrate Center", state="normal")
        self.log_message(f"センターキャリブレーション完了: 右目オフセット({rx:.2f}, {ry:.2f}) 左目オフセット({lx:.2f}, {ly:.2f}) を設定しました。")

    def reset_calibration(self):
        with state_lock:
            self.config["calibration"] = DEFAULT_CONFIG["calibration"].copy()
        self.log_message("キャリブレーション設定を初期値にリセットしました。")

    def create_sleep_section(self, parent):
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

    def on_sleep_change(self, event=None):
        with state_lock:
            self.config["sleep_mode"]["enabled"] = self.sleep_enabled.get()
            try: self.config["sleep_mode"]["timeout_seconds"] = float(self.timeout_entry.get())
            except: pass
            try: self.config["sleep_mode"]["change_threshold"] = float(self.threshold_entry.get())
            except: pass
            try: self.config["sleep_mode"]["closed_value"] = float(self.closed_val_entry.get())
            except: pass

    def reset_sleep(self):
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
        self.log_message("スリープモード設定を初期値にリセットしました。")

    def update_status(self):
        mps, is_sleeping = self.handler.get_status()
        self.status_label.configure(text=f"Messages / sec: {mps}")
        
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

    def create_steamvr_section(self, parent):
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="SteamVR Settings", font=("Arial", 16, "bold")).pack(side="left")
        
        self.steamvr_enabled = ctk.BooleanVar(value=self.config["steamvr"]["auto_register"])
        cb = ctk.CTkCheckBox(section, text="Auto-Register Manifest on Startup", variable=self.steamvr_enabled, command=self.on_steamvr_change)
        cb.pack(anchor="w", padx=20, pady=10)

    def on_steamvr_change(self):
        with state_lock:
            self.config["steamvr"]["auto_register"] = self.steamvr_enabled.get()
