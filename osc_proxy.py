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
        "gaze_x": {
            "right_out": { "right_in": 1.0, "left_in": 0.0 },
            "left_out":  { "right_in": 1.0, "left_in": 0.0 }
        },
        "gaze_y": {
            "right_out": { "right_in": 1.0, "left_in": 0.0 },
            "left_out":  { "right_in": 1.0, "left_in": 0.0 }
        }
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
            config["mix"].update(user_config["mix"])
        return config
    except Exception as e:
        print(f"Error reading config.json: {e}. Using default settings.")
        return DEFAULT_CONFIG

config = load_config()

client = udp_client.SimpleUDPClient(IP_ADDRESS, SEND_PORT)

# 状態管理変数
state_lock = threading.Lock()
last_eye_value = None
last_change_time = time.time()
is_sleeping = False
msg_sent_count = 0

in_right_lid = 0.0
in_left_lid = 0.0
in_right_gaze_x = 0.0
in_left_gaze_x = 0.0
in_right_gaze_y = 0.0
in_left_gaze_y = 0.0

def default_handler(address, *args):
    global last_eye_value, last_change_time, is_sleeping, msg_sent_count
    global in_right_lid, in_left_lid, in_right_gaze_x, in_left_gaze_x, in_right_gaze_y, in_left_gaze_y

    incoming_value = args[0] if len(args) > 0 else 0.0
    current_time = time.time()

    if "RightEyeLid" in address or "LeftEyeLid" in address:
        with state_lock:
            if "RightEyeLid" in address:
                in_right_lid = incoming_value
                if config["sleep_mode"]["enabled"]:
                    if last_eye_value is None or abs(incoming_value - last_eye_value) >= config["sleep_mode"]["change_threshold"]:
                        last_eye_value = incoming_value
                        last_change_time = current_time
                        is_sleeping = False
                    else:
                        if current_time - last_change_time >= config["sleep_mode"]["timeout_seconds"]:
                            is_sleeping = True
                else:
                    last_eye_value = incoming_value
                    is_sleeping = False
            else:
                in_left_lid = incoming_value
            
            mix_cfg = config["mix"]["eyelid"]
            out_right = in_right_lid * mix_cfg["right_out"]["right_in"] + in_left_lid * mix_cfg["right_out"]["left_in"]
            out_left  = in_right_lid * mix_cfg["left_out"]["right_in"]  + in_left_lid * mix_cfg["left_out"]["left_in"]
            
            if config["sleep_mode"]["enabled"] and is_sleeping:
                out_right = config["sleep_mode"]["closed_value"]
                out_left = config["sleep_mode"]["closed_value"]

        if "RightEyeLid" in address:
            r_addr = address
            l_addr = address.replace("RightEyeLid", "LeftEyeLid")
        else:
            l_addr = address
            r_addr = address.replace("LeftEyeLid", "RightEyeLid")

        out_r = list(args)
        if len(out_r) > 0: out_r[0] = out_right
        else: out_r = [out_right]
        
        out_l = list(args)
        if len(out_l) > 0: out_l[0] = out_left
        else: out_l = [out_left]
        
        client.send_message(r_addr, out_r)
        client.send_message(l_addr, out_l)
        with state_lock:
            msg_sent_count += 2

    elif any(k in address for k in ["RightEyeX", "EyeRightX", "LeftEyeX", "EyeLeftX"]):
        is_right = "RightEyeX" in address or "EyeRightX" in address
        with state_lock:
            if is_right:
                in_right_gaze_x = incoming_value
            else:
                in_left_gaze_x = incoming_value
                
            mix_cfg = config["mix"]["gaze_x"]
            out_right = in_right_gaze_x * mix_cfg["right_out"]["right_in"] + in_left_gaze_x * mix_cfg["right_out"]["left_in"]
            out_left  = in_right_gaze_x * mix_cfg["left_out"]["right_in"]  + in_left_gaze_x * mix_cfg["left_out"]["left_in"]

        if is_right:
            r_addr = address
            l_addr = address.replace("RightEyeX", "LeftEyeX") if "RightEyeX" in address else address.replace("EyeRightX", "EyeLeftX")
        else:
            l_addr = address
            r_addr = address.replace("LeftEyeX", "RightEyeX") if "LeftEyeX" in address else address.replace("EyeLeftX", "EyeRightX")

        out_r = list(args)
        if len(out_r) > 0: out_r[0] = out_right
        else: out_r = [out_right]
        
        out_l = list(args)
        if len(out_l) > 0: out_l[0] = out_left
        else: out_l = [out_left]

        client.send_message(r_addr, out_r)
        client.send_message(l_addr, out_l)
        with state_lock:
            msg_sent_count += 2

    elif any(k in address for k in ["RightEyeY", "EyeRightY", "LeftEyeY", "EyeLeftY"]):
        is_right = "RightEyeY" in address or "EyeRightY" in address
        with state_lock:
            if is_right:
                in_right_gaze_y = incoming_value
            else:
                in_left_gaze_y = incoming_value
                
            mix_cfg = config["mix"]["gaze_y"]
            out_right = in_right_gaze_y * mix_cfg["right_out"]["right_in"] + in_left_gaze_y * mix_cfg["right_out"]["left_in"]
            out_left  = in_right_gaze_y * mix_cfg["left_out"]["right_in"]  + in_left_gaze_y * mix_cfg["left_out"]["left_in"]

        if is_right:
            r_addr = address
            l_addr = address.replace("RightEyeY", "LeftEyeY") if "RightEyeY" in address else address.replace("EyeRightY", "EyeLeftY")
        else:
            l_addr = address
            r_addr = address.replace("LeftEyeY", "RightEyeY") if "LeftEyeY" in address else address.replace("EyeLeftY", "EyeRightY")

        out_r = list(args)
        if len(out_r) > 0: out_r[0] = out_right
        else: out_r = [out_right]
        
        out_l = list(args)
        if len(out_l) > 0: out_l[0] = out_left
        else: out_l = [out_left]

        client.send_message(r_addr, out_r)
        client.send_message(l_addr, out_l)
        with state_lock:
            msg_sent_count += 2

    else:
        client.send_message(address, args)
        with state_lock:
            msg_sent_count += 1

class OSCProxyGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OSC Proxy Configuration")
        self.geometry("600x650")
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=10, pady=10, fill="both", expand=True)
        
        self.tabview.add("Eyelid")
        self.tabview.add("Gaze X")
        self.tabview.add("Gaze Y")
        self.tabview.add("Sleep Mode")
        
        self.sliders = {}
        
        self.create_mix_tab("Eyelid", "eyelid")
        self.create_mix_tab("Gaze X", "gaze_x")
        self.create_mix_tab("Gaze Y", "gaze_y")
        self.create_sleep_tab()
        
        save_btn = ctk.CTkButton(self, text="Save Config", command=self.save_config)
        save_btn.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self, text="Messages / sec: 0 | Sleep: OFF", font=("Arial", 12))
        self.status_label.pack(pady=5)
        self.update_status()

    def create_mix_tab(self, tab_name, config_key):
        tab = self.tabview.tab(tab_name)
        
        for side_out in ["right_out", "left_out"]:
            frame = ctk.CTkFrame(tab)
            frame.pack(fill="x", padx=10, pady=10)
            
            label = ctk.CTkLabel(frame, text=f"Output: {side_out.replace('_', ' ').title()}", font=("Arial", 14, "bold"))
            label.pack(anchor="w", padx=10, pady=5)
            
            for side_in in ["right_in", "left_in"]:
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=10, pady=2)
                
                lbl = ctk.CTkLabel(row, text=f"From {side_in.replace('_', ' ').title()}:", width=120, anchor="e")
                lbl.pack(side="left", padx=5)
                
                slider = ctk.CTkSlider(row, from_=-1.0, to=1.0, command=lambda v, k=config_key, o=side_out, i=side_in: self.on_mix_change(v, k, o, i))
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

    def create_sleep_tab(self):
        tab = self.tabview.tab("Sleep Mode")
        
        self.sleep_enabled = ctk.BooleanVar(value=config["sleep_mode"]["enabled"])
        cb = ctk.CTkCheckBox(tab, text="Enable Sleep Mode", variable=self.sleep_enabled, command=self.on_sleep_change)
        cb.pack(anchor="w", padx=20, pady=10)
        
        # Timeout
        row1 = ctk.CTkFrame(tab, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row1, text="Timeout (sec):", width=120, anchor="e").pack(side="left", padx=5)
        self.timeout_entry = ctk.CTkEntry(row1)
        self.timeout_entry.insert(0, str(config["sleep_mode"]["timeout_seconds"]))
        self.timeout_entry.pack(side="left", fill="x", expand=True)
        self.timeout_entry.bind("<KeyRelease>", self.on_sleep_change)
        
        # Threshold
        row2 = ctk.CTkFrame(tab, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row2, text="Change Threshold:", width=120, anchor="e").pack(side="left", padx=5)
        self.threshold_entry = ctk.CTkEntry(row2)
        self.threshold_entry.insert(0, str(config["sleep_mode"]["change_threshold"]))
        self.threshold_entry.pack(side="left", fill="x", expand=True)
        self.threshold_entry.bind("<KeyRelease>", self.on_sleep_change)

        # Closed value
        row3 = ctk.CTkFrame(tab, fg_color="transparent")
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

    def save_config(self):
        with state_lock:
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print("Config saved successfully.")
            except Exception as e:
                print(f"Error saving config: {e}")

    def update_status(self):
        global msg_sent_count
        with state_lock:
            mps = msg_sent_count
            msg_sent_count = 0
            sleep_status = "ON" if is_sleeping else "OFF"
        self.status_label.configure(text=f"Messages / sec: {mps} | Sleep: {sleep_status}")
        self.after(1000, self.update_status)

def monitor_steamvr(server):
    time.sleep(10)
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
    disp.set_default_handler(default_handler)

    try:
        server = osc_server.ThreadingOSCUDPServer((IP_ADDRESS, RECEIVE_PORT), disp)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or "10048" in str(e) or "Address already in use" in str(e):
            resolved = False
            try:
                for conn in psutil.net_connections(kind='udp'):
                    if conn.laddr and conn.laddr.port == RECEIVE_PORT:
                        pid = conn.pid
                        if pid:
                            try:
                                proc = psutil.Process(pid)
                                cmdline = proc.cmdline()
                                is_proxy = any("osc_proxy" in cmd.lower() for cmd in cmdline) if cmdline else False
                                if "osc_proxy" in proc.name().lower():
                                    is_proxy = True
                                    
                                if is_proxy:
                                    print(f"\n[エラー] ポート {RECEIVE_PORT} は既に別の OSC Proxy (PID: {pid}) によって使用されています。")
                                    ans = input("以前のプロセスを終了して新しく起動しますか？ (y/n): ")
                                    if ans.lower() in ['y', 'yes']:
                                        proc.terminate()
                                        proc.wait(timeout=3)
                                        print("古いプロセスを終了しました。再起動します...\n")
                                        server = osc_server.ThreadingOSCUDPServer((IP_ADDRESS, RECEIVE_PORT), disp)
                                        resolved = True
                                    else:
                                        print("起動を中止します。")
                                        sys.exit(1)
                                else:
                                    print(f"\n[エラー] ポート {RECEIVE_PORT} は別のプロセス (PID: {pid}, {proc.name()}) によって使用されています。")
                                    sys.exit(1)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
            except psutil.AccessDenied:
                print(f"\n[エラー] ポート {RECEIVE_PORT} が既に使用されています。プロセスの特定には管理者権限が必要です。")
                sys.exit(1)
            
            if not resolved:
                print(f"\n[エラー] ポート {RECEIVE_PORT} が既に使用されています（プロセスの特定または停止ができませんでした）。")
                sys.exit(1)
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
    app = OSCProxyGUI()
    app.mainloop()
    
    server.shutdown()
    print("\nOSC Proxy shut down successfully.")
