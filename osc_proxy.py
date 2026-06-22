import threading
import time
import psutil
import os
import sys
import json
import customtkinter as ctk
from pythonosc import dispatcher, osc_server, udp_client

# 受信ポート（Baballoniaからの送信先ポートに合わせる）
RECEIVE_PORT = 8887
# 送信ポート（VRChatまたはVRCFaceTrackingの受信ポート）
SEND_PORT = 8888
IP_ADDRESS = "127.0.0.1"

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "sleep_mode": {
        "enabled": True,
        "timeout_seconds": 300.0,
        "change_threshold": 0.20,
        "closed_value": 0.0
    },
    "mix": {
        "eyelid": {
            "right_out": { "right_in": 1.0, "left_in": 0.0 },
            "left_out":  { "right_in": 1.0, "left_in": 0.0 }
        },
        "gaze": {
            "right_out": { "right_in": 1.0, "left_in": 0.0 },
            "left_out":  { "right_in": 1.0, "left_in": 0.0 }
        }
    },
    "calibration": {
        "right_gaze_x_offset": 0.0,
        "left_gaze_x_offset": 0.0,
        "right_gaze_y_offset": 0.0,
        "left_gaze_y_offset": 0.0
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception as e:
            print(f"Error creating config.json: {e}")
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            
        config = DEFAULT_CONFIG.copy()
        if "sleep_mode" in user_config:
            config["sleep_mode"].update(user_config["sleep_mode"])
        if "mix" in user_config:
            if "gaze_x" in user_config["mix"] and "gaze" not in user_config["mix"]:
                config["mix"]["gaze"] = user_config["mix"]["gaze_x"]
            config["mix"].update(user_config["mix"])
            config["mix"].pop("gaze_x", None)
            config["mix"].pop("gaze_y", None)
        if "calibration" in user_config:
            config["calibration"].update(user_config["calibration"])
        return config
    except Exception as e:
        print(f"Error reading config.json: {e}. Using default settings.")
        return DEFAULT_CONFIG

config = load_config()
client = udp_client.SimpleUDPClient(IP_ADDRESS, SEND_PORT)
state_lock = threading.Lock()

class OSCMessageHandler:
    def __init__(self, client, config, lock):
        self.client = client
        self.config = config
        self.lock = lock
        
        self.last_eye_value = None
        self.last_change_time = time.time()
        self.is_sleeping = False
        self.msg_sent_count = 0
        
        self.in_right_lid = 0.0
        self.in_left_lid = 0.0
        
        self.raw_right_gaze_x = 0.0
        self.raw_left_gaze_x = 0.0
        self.raw_right_gaze_y = 0.0
        self.raw_left_gaze_y = 0.0

    def get_status(self):
        with self.lock:
            count = self.msg_sent_count
            self.msg_sent_count = 0
            is_sleeping = self.is_sleeping
        return count, is_sleeping

    def get_raw_gaze(self):
        with self.lock:
            return self.raw_right_gaze_x, self.raw_left_gaze_x, self.raw_right_gaze_y, self.raw_left_gaze_y

    def handle(self, address, *args):
        incoming_value = args[0] if len(args) > 0 else 0.0
        current_time = time.time()

        if "RightEyeLid" in address or "LeftEyeLid" in address:
            self._handle_eyelid(address, incoming_value, current_time, args)
        elif any(k in address for k in ["RightEyeX", "EyeRightX", "LeftEyeX", "EyeLeftX"]):
            self._handle_gaze_x(address, incoming_value, args)
        elif any(k in address for k in ["RightEyeY", "EyeRightY", "LeftEyeY", "EyeLeftY"]):
            self._handle_gaze_y(address, incoming_value, args)
        else:
            self._handle_default(address, args)

    def _handle_eyelid(self, address, incoming_value, current_time, args):
        with self.lock:
            if "RightEyeLid" in address:
                self.in_right_lid = incoming_value
                self._update_sleep_state(incoming_value, current_time)
            else:
                self.in_left_lid = incoming_value
            
            mix_cfg = self.config["mix"]["eyelid"]
            out_right = self.in_right_lid * mix_cfg["right_out"]["right_in"] + self.in_left_lid * mix_cfg["right_out"]["left_in"]
            out_left  = self.in_right_lid * mix_cfg["left_out"]["right_in"]  + self.in_left_lid * mix_cfg["left_out"]["left_in"]
            
            if self.config["sleep_mode"]["enabled"] and self.is_sleeping:
                out_right = self.config["sleep_mode"]["closed_value"]
                out_left = self.config["sleep_mode"]["closed_value"]

        self._send_mixed_messages(address, "RightEyeLid", "LeftEyeLid", out_right, out_left, args)

    def _update_sleep_state(self, incoming_value, current_time):
        if self.config["sleep_mode"]["enabled"]:
            if self.last_eye_value is None or abs(incoming_value - self.last_eye_value) >= self.config["sleep_mode"]["change_threshold"]:
                self.last_eye_value = incoming_value
                self.last_change_time = current_time
                self.is_sleeping = False
            else:
                if current_time - self.last_change_time >= self.config["sleep_mode"]["timeout_seconds"]:
                    self.is_sleeping = True
        else:
            self.last_eye_value = incoming_value
            self.is_sleeping = False

    def _handle_gaze_x(self, address, incoming_value, args):
        is_right = "RightEyeX" in address or "EyeRightX" in address
        with self.lock:
            if is_right:
                self.raw_right_gaze_x = incoming_value
            else:
                self.raw_left_gaze_x = incoming_value
                
            calib_rx = self.raw_right_gaze_x - self.config["calibration"]["right_gaze_x_offset"]
            calib_lx = self.raw_left_gaze_x - self.config["calibration"]["left_gaze_x_offset"]
            
            mix_cfg = self.config["mix"]["gaze"]
            out_right = calib_rx * mix_cfg["right_out"]["right_in"] + calib_lx * mix_cfg["right_out"]["left_in"]
            out_left  = calib_rx * mix_cfg["left_out"]["right_in"]  + calib_lx * mix_cfg["left_out"]["left_in"]

        self._send_gaze_messages(address, is_right, "EyeX", out_right, out_left, args)

    def _handle_gaze_y(self, address, incoming_value, args):
        is_right = "RightEyeY" in address or "EyeRightY" in address
        with self.lock:
            if is_right:
                self.raw_right_gaze_y = incoming_value
            else:
                self.raw_left_gaze_y = incoming_value
                
            calib_ry = self.raw_right_gaze_y - self.config["calibration"]["right_gaze_y_offset"]
            calib_ly = self.raw_left_gaze_y - self.config["calibration"]["left_gaze_y_offset"]
            
            mix_cfg = self.config["mix"]["gaze"]
            out_right = calib_ry * mix_cfg["right_out"]["right_in"] + calib_ly * mix_cfg["right_out"]["left_in"]
            out_left  = calib_ry * mix_cfg["left_out"]["right_in"]  + calib_ly * mix_cfg["left_out"]["left_in"]

        self._send_gaze_messages(address, is_right, "EyeY", out_right, out_left, args)

    def _send_gaze_messages(self, address, is_right, axis_suffix, out_right, out_left, args):
        if axis_suffix == "EyeX":
            right_keys = ["RightEyeX", "EyeRightX"]
            left_keys = ["LeftEyeX", "EyeLeftX"]
        else:
            right_keys = ["RightEyeY", "EyeRightY"]
            left_keys = ["LeftEyeY", "EyeLeftY"]
            
        r_addr = address
        l_addr = address
        
        if is_right:
            for r_key, l_key in zip(right_keys, left_keys):
                if r_key in address:
                    l_addr = address.replace(r_key, l_key)
                    break
        else:
            for l_key, r_key in zip(left_keys, right_keys):
                if l_key in address:
                    r_addr = address.replace(l_key, r_key)
                    break

        self._send_mixed_messages(None, None, None, out_right, out_left, args, r_addr=r_addr, l_addr=l_addr)

    def _send_mixed_messages(self, address, right_key, left_key, out_right, out_left, args, r_addr=None, l_addr=None):
        if r_addr is None or l_addr is None:
            if right_key in address:
                r_addr = address
                l_addr = address.replace(right_key, left_key)
            else:
                l_addr = address
                r_addr = address.replace(left_key, right_key)

        out_r = list(args)
        if len(out_r) > 0: out_r[0] = out_right
        else: out_r = [out_right]
        
        out_l = list(args)
        if len(out_l) > 0: out_l[0] = out_left
        else: out_l = [out_left]
        
        self.client.send_message(r_addr, out_r)
        self.client.send_message(l_addr, out_l)
        
        with self.lock:
            self.msg_sent_count += 2

    def _handle_default(self, address, args):
        self.client.send_message(address, args)
        with self.lock:
            self.msg_sent_count += 1

class OSCProxyGUI(ctk.CTk):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler
        self.title("OSC Proxy Configuration")
        self.geometry("850x600")
        self.resizable(False, False)
        
        # Banner
        self.banner_frame = ctk.CTkFrame(self, fg_color="#388E3C", height=45)
        self.banner_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.banner_frame.pack_propagate(False)
        self.banner_label = ctk.CTkLabel(self.banner_frame, text="STATUS: ACTIVE", font=("Arial", 20, "bold"), text_color="white")
        self.banner_label.pack(expand=True)
        
        # Main Layout
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
        
        # Status Label and Save Button
        bottom_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=10)
        
        self.status_label = ctk.CTkLabel(bottom_frame, text="Messages / sec: 0", font=("Arial", 12))
        self.status_label.pack(pady=5)
        
        save_btn = ctk.CTkButton(bottom_frame, text="Save Config to File", font=("Arial", 16, "bold"), height=45, command=self.save_config)
        save_btn.pack(fill="x")
        
        self.update_status()

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
                slider.set(config["mix"][config_key][side_out][side_in])
                slider.pack(side="left", fill="x", expand=True, padx=5)
                
                val_lbl = ctk.CTkLabel(row, text=f"{slider.get():.2f}", width=40)
                val_lbl.pack(side="left")
                
                self.sliders[f"{config_key}_{side_out}_{side_in}"] = (slider, val_lbl)

    def on_mix_change(self, value, config_key, side_out, side_in):
        val = float(value)
        with state_lock:
            config["mix"][config_key][side_out][side_in] = val
        slider, val_lbl = self.sliders[f"{config_key}_{side_out}_{side_in}"]
        val_lbl.configure(text=f"{val:.2f}")

    def reset_mix(self, config_key):
        default = DEFAULT_CONFIG["mix"][config_key]
        for side_out in ["right_out", "left_out"]:
            for side_in in ["right_in", "left_in"]:
                val = default[side_out][side_in]
                with state_lock:
                    config["mix"][config_key][side_out][side_in] = val
                slider, val_lbl = self.sliders[f"{config_key}_{side_out}_{side_in}"]
                slider.set(val)
                val_lbl.configure(text=f"{val:.2f}")

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
            config["calibration"]["right_gaze_x_offset"] = rx
            config["calibration"]["left_gaze_x_offset"] = lx
            config["calibration"]["right_gaze_y_offset"] = ry
            config["calibration"]["left_gaze_y_offset"] = ly
        self.calib_btn.configure(text="Calibrate Center", state="normal")

    def reset_calibration(self):
        with state_lock:
            config["calibration"] = DEFAULT_CONFIG["calibration"].copy()

    def create_sleep_section(self, parent):
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Sleep Mode", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Reset", width=60, height=24, command=self.reset_sleep).pack(side="right")
        
        self.sleep_enabled = ctk.BooleanVar(value=config["sleep_mode"]["enabled"])
        cb = ctk.CTkCheckBox(section, text="Enable Sleep Mode", variable=self.sleep_enabled, command=self.on_sleep_change)
        cb.pack(anchor="w", padx=20, pady=10)
        
        row1 = ctk.CTkFrame(section, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row1, text="Timeout (sec):", width=120, anchor="e").pack(side="left", padx=5)
        self.timeout_entry = ctk.CTkEntry(row1)
        self.timeout_entry.insert(0, str(config["sleep_mode"]["timeout_seconds"]))
        self.timeout_entry.pack(side="left", fill="x", expand=True)
        self.timeout_entry.bind("<KeyRelease>", self.on_sleep_change)
        
        row2 = ctk.CTkFrame(section, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row2, text="Change Threshold:", width=120, anchor="e").pack(side="left", padx=5)
        self.threshold_entry = ctk.CTkEntry(row2)
        self.threshold_entry.insert(0, str(config["sleep_mode"]["change_threshold"]))
        self.threshold_entry.pack(side="left", fill="x", expand=True)
        self.threshold_entry.bind("<KeyRelease>", self.on_sleep_change)

        row3 = ctk.CTkFrame(section, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row3, text="Closed Value:", width=120, anchor="e").pack(side="left", padx=5)
        self.closed_val_entry = ctk.CTkEntry(row3)
        self.closed_val_entry.insert(0, str(config["sleep_mode"]["closed_value"]))
        self.closed_val_entry.pack(side="left", fill="x", expand=True)
        self.closed_val_entry.bind("<KeyRelease>", self.on_sleep_change)

    def on_sleep_change(self, event=None):
        with state_lock:
            config["sleep_mode"]["enabled"] = self.sleep_enabled.get()
            try: config["sleep_mode"]["timeout_seconds"] = float(self.timeout_entry.get())
            except: pass
            try: config["sleep_mode"]["change_threshold"] = float(self.threshold_entry.get())
            except: pass
            try: config["sleep_mode"]["closed_value"] = float(self.closed_val_entry.get())
            except: pass

    def reset_sleep(self):
        default = DEFAULT_CONFIG["sleep_mode"]
        with state_lock:
            config["sleep_mode"] = default.copy()
        
        self.sleep_enabled.set(default["enabled"])
        self.timeout_entry.delete(0, 'end')
        self.timeout_entry.insert(0, str(default["timeout_seconds"]))
        self.threshold_entry.delete(0, 'end')
        self.threshold_entry.insert(0, str(default["change_threshold"]))
        self.closed_val_entry.delete(0, 'end')
        self.closed_val_entry.insert(0, str(default["closed_value"]))

    def save_config(self):
        with state_lock:
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print("Config saved successfully.")
            except Exception as e:
                print(f"Error saving config: {e}")

    def update_status(self):
        mps, is_sleeping = self.handler.get_status()
        self.status_label.configure(text=f"Messages / sec: {mps}")
        
        if is_sleeping:
            self.banner_frame.configure(fg_color="#D32F2F") # Red
            self.banner_label.configure(text="STATUS: SLEEPING")
        else:
            self.banner_frame.configure(fg_color="#388E3C") # Green
            self.banner_label.configure(text="STATUS: ACTIVE")
            
        self.after(500, self.update_status)

def resolve_port_conflict(port, disp):
    try:
        for conn in psutil.net_connections(kind='udp'):
            if conn.laddr and conn.laddr.port == port:
                pid = conn.pid
                if not pid:
                    continue
                try:
                    proc = psutil.Process(pid)
                    cmdline = proc.cmdline()
                    is_proxy = any("osc_proxy" in cmd.lower() for cmd in cmdline) if cmdline else False
                    if "osc_proxy" in proc.name().lower():
                        is_proxy = True
                        
                    if is_proxy:
                        print(f"\n[エラー] ポート {port} は既に別の OSC Proxy (PID: {pid}) によって使用されています。")
                        ans = input("以前のプロセスを終了して新しく起動しますか？ (y/n): ")
                        if ans.lower() in ['y', 'yes']:
                            proc.terminate()
                            proc.wait(timeout=3)
                            print("古いプロセスを終了しました。再起動します...\n")
                            return osc_server.ThreadingOSCUDPServer((IP_ADDRESS, port), disp)
                        else:
                            print("起動を中止します。")
                            sys.exit(1)
                    else:
                        print(f"\n[エラー] ポート {port} は別のプロセス (PID: {pid}, {proc.name()}) によって使用されています。")
                        sys.exit(1)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except psutil.AccessDenied:
        print(f"\n[エラー] ポート {port} が既に使用されています。プロセスの特定には管理者権限が必要です。")
        sys.exit(1)
        
    print(f"\n[エラー] ポート {port} が既に使用されています（プロセスの特定または停止ができませんでした）。")
    sys.exit(1)

def monitor_steamvr(server):
    time.sleep(30)
    while True:
        is_running = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'vrserver.exe':
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if not is_running:
            server.shutdown()
            os._exit(0) # Also terminate the GUI if steamvr is closed
        time.sleep(5)

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    disp = dispatcher.Dispatcher()
    handler = OSCMessageHandler(client, config, state_lock)
    disp.set_default_handler(handler.handle)

    try:
        server = osc_server.ThreadingOSCUDPServer((IP_ADDRESS, RECEIVE_PORT), disp)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or "10048" in str(e) or "Address already in use" in str(e):
            server = resolve_port_conflict(RECEIVE_PORT, disp)
        else:
            raise

    # SteamVR監視用のバックグラウンドスレッドを開始
    monitor_thread = threading.Thread(target=monitor_steamvr, args=(server,), daemon=True)
    monitor_thread.start()

    # OSCサーバーをバックグラウンドで開始
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"[{time.strftime('%H:%M:%S')}] OSC Proxy started with GUI.")
    
    # メインスレッドでGUIを実行
    app = OSCProxyGUI(handler)
    app.mainloop()
    
    server.shutdown()
    print("\nOSC Proxy shut down successfully.")
