import threading
import time
import psutil
import os
import sys
import json
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
    "sync": {
        "eyelid_enabled": True,
        "gaze_enabled": True
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
        if "sync" in user_config:
            config["sync"].update(user_config["sync"])
        return config
    except Exception as e:
        print(f"Error reading config.json: {e}. Using default settings.")
        return DEFAULT_CONFIG

config = load_config()

client = udp_client.SimpleUDPClient(IP_ADDRESS, SEND_PORT)

# 状態管理変数
state_lock = threading.Lock()
last_eye_value = None
last_gaze_x = None
last_gaze_y = None
last_change_time = time.time()
is_sleeping = False
msg_sent_count = 0
event_logs = []

def default_handler(address, *args):
    global last_eye_value, last_gaze_x, last_gaze_y, last_change_time, is_sleeping, msg_sent_count

    if "RightEyeLid" in address:
        current_time = time.time()
        
        # 受信した目のパラメータ値を取得 (通常はfloat)
        incoming_value = args[0] if len(args) > 0 else 0.0

        with state_lock:
            if config["sleep_mode"]["enabled"]:
                # 初回データまたは一定以上の変化があった場合
                if last_eye_value is None or abs(incoming_value - last_eye_value) >= config["sleep_mode"]["change_threshold"]:
                    last_eye_value = incoming_value
                    last_change_time = current_time
                    if is_sleeping:
                        event_logs.append(f"[{time.strftime('%H:%M:%S')}] Eye movement detected. Exiting sleep mode.")
                        if len(event_logs) > 5: event_logs.pop(0)
                    is_sleeping = False
                else:
                    # 一定時間変化がないかチェック
                    if current_time - last_change_time >= config["sleep_mode"]["timeout_seconds"]:
                        if not is_sleeping:
                            event_logs.append(f"[{time.strftime('%H:%M:%S')}] No eye movement for {config['sleep_mode']['timeout_seconds']}s. Entering sleep mode.")
                            if len(event_logs) > 5: event_logs.pop(0)
                        is_sleeping = True
                
                # スリープ中なら目を閉じた値に固定、そうでなければ受信した値をそのまま使用
                output_value = config["sleep_mode"]["closed_value"] if is_sleeping else incoming_value
            else:
                last_eye_value = incoming_value
                is_sleeping = False
                output_value = incoming_value

        # 元の引数リストをコピーして、最初の値をoutput_valueに置き換える
        output_args = list(args)
        if len(output_args) > 0:
            output_args[0] = output_value
        else:
            output_args = [output_value]
            
        if config["sync"]["eyelid_enabled"]:
            left_address = address.replace("RightEyeLid", "LeftEyeLid")
            client.send_message(left_address, output_args)
            client.send_message(address, output_args)
            with state_lock:
                msg_sent_count += 2
        else:
            client.send_message(address, output_args)
            with state_lock:
                msg_sent_count += 1

    elif "LeftEyeLid" in address:
        if config["sync"]["eyelid_enabled"]:
            # 左目のデータは右目のデータで上書きするため無視
            pass
        else:
            incoming_value = args[0] if len(args) > 0 else 0.0
            with state_lock:
                output_value = config["sleep_mode"]["closed_value"] if is_sleeping and config["sleep_mode"]["enabled"] else incoming_value
            output_args = list(args)
            if len(output_args) > 0:
                output_args[0] = output_value
            else:
                output_args = [output_value]
            client.send_message(address, output_args)
            with state_lock:
                msg_sent_count += 1

    elif any(k in address for k in ["RightEyeX", "EyeRightX"]):
        incoming_value = args[0] if len(args) > 0 else 0.0
        with state_lock:
            last_gaze_x = incoming_value
            
        if config["sync"]["gaze_enabled"]:
            left_address = address.replace("RightEyeX", "LeftEyeX") if "RightEyeX" in address else address.replace("EyeRightX", "EyeLeftX")
            client.send_message(left_address, args)
            client.send_message(address, args)
            with state_lock:
                msg_sent_count += 2
        else:
            client.send_message(address, args)
            with state_lock:
                msg_sent_count += 1

    elif any(k in address for k in ["RightEyeY", "EyeRightY"]):
        incoming_value = args[0] if len(args) > 0 else 0.0
        with state_lock:
            last_gaze_y = incoming_value
            
        if config["sync"]["gaze_enabled"]:
            left_address = address.replace("RightEyeY", "LeftEyeY") if "RightEyeY" in address else address.replace("EyeRightY", "EyeLeftY")
            client.send_message(left_address, args)
            client.send_message(address, args)
            with state_lock:
                msg_sent_count += 2
        else:
            client.send_message(address, args)
            with state_lock:
                msg_sent_count += 1

    elif any(k in address for k in ["LeftEyeX", "LeftEyeY", "EyeLeftX", "EyeLeftY"]):
        if config["sync"]["gaze_enabled"]:
            # 左目の視線データは右目のデータで上書きするため無視
            pass
        else:
            client.send_message(address, args)
            with state_lock:
                msg_sent_count += 1

    else:
        client.send_message(address, args)
        with state_lock:
            msg_sent_count += 1

def ui_loop():
    global msg_sent_count
    os.system("") # WindowsコマンドプロンプトでANSIエスケープシーケンスを有効化
    last_lines_count = 0
    
    while True:
        time.sleep(1.0)
        with state_lock:
            mps = msg_sent_count
            msg_sent_count = 0
            current_sleep = is_sleeping
            current_eye = last_eye_value
            current_gaze_x = last_gaze_x
            current_gaze_y = last_gaze_y
            last_change = last_change_time
            logs = list(event_logs)
            
        time_since_change = time.time() - last_change if current_eye is not None else 0
        
        ui_text = (
            f"=== OSC Proxy Dashboard ===\n"
            f"Port: Listen({RECEIVE_PORT}) -> Send({SEND_PORT})\n"
            f"---------------------------\n"
            f"Messages / sec: {mps}\n"
            f"Sleep Mode:     {'[ ON ] (Eyes Closed)' if current_sleep else '[ OFF ] (Active)'}\n"
            f"Last Eye Move:  {time_since_change:.1f}s ago (Timeout: {config['sleep_mode']['timeout_seconds']}s)\n"
        )
        
        if current_eye is not None:
            output_val = config["sleep_mode"]["closed_value"] if current_sleep and config["sleep_mode"]["enabled"] else current_eye
            ui_text += f"Current Eye:    In={current_eye:.3f} | Out={output_val:.3f}\n"
        else:
            ui_text += f"Current Eye:    Waiting for data...\n"
            
        if current_gaze_x is not None or current_gaze_y is not None:
            gx = current_gaze_x if current_gaze_x is not None else 0.0
            gy = current_gaze_y if current_gaze_y is not None else 0.0
            ui_text += f"Current Gaze:   X={gx:+.3f} | Y={gy:+.3f}\n"
        else:
            ui_text += f"Current Gaze:   Waiting for data...\n"
            
        ui_text += "---------------------------\n"
        ui_text += "Recent Events:\n"
        if not logs:
            ui_text += " No events yet.\n"
        for log in logs:
            ui_text += f" {log}\n"
            
        # 前回描画した行数分カーソルを上に移動し、そこから下を消去する
        if last_lines_count > 0:
            sys.stdout.write(f"\033[{last_lines_count}F\033[J")
            
        sys.stdout.write(ui_text)
        sys.stdout.flush()
        
        last_lines_count = ui_text.count('\n')

def monitor_steamvr(server):
    # SteamVRの起動直後はプロセスが完全に立ち上がっていない可能性があるため少し待機
    time.sleep(10)
    
    while True:
        is_running = False
        # 実行中のすべてのプロセス名を取得して確認
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'vrserver.exe':
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # SteamVRが終了していたらサーバーをシャットダウンしてループを抜ける
        if not is_running:
            server.shutdown()
            break
        
        # 5秒間隔でチェック
        time.sleep(5)

if __name__ == "__main__":
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

    # UI用のバックグラウンドスレッドを開始
    ui_thread = threading.Thread(target=ui_loop, daemon=True)
    ui_thread.start()

    with state_lock:
        event_logs.append(f"[{time.strftime('%H:%M:%S')}] OSC Proxy started.")
    
    # ここでブロックされ、OSCの受信を続ける（server.shutdown()が呼ばれるまで）
    server.serve_forever()
    
    print("\nOSC Proxy shut down successfully.")