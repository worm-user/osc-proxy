import threading
import time
import psutil
import os
import sys
from pythonosc import dispatcher, osc_server, udp_client

# 受信ポート（Baballoniaからの送信先ポートに合わせる）
RECEIVE_PORT = 8887
# 送信ポート（VRChatまたはVRCFaceTrackingの受信ポート）
SEND_PORT = 8888
IP_ADDRESS = "127.0.0.1"

# --- スリープモード（自動目閉じ）設定 ---
SLEEP_TIMEOUT = 300.0       # この秒数以上変化がなければスリープモードに入る（例: 60秒）
CHANGE_THRESHOLD = 0.20     # これ以上パラメータが変化したら「変化した」とみなす閾値
CLOSED_VALUE = 0.0          # 目を閉じた状態のパラメータ値（アバターや設定によって 0.0 または 1.0 に変更してください）

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
            # 初回データまたは一定以上の変化があった場合
            if last_eye_value is None or abs(incoming_value - last_eye_value) >= CHANGE_THRESHOLD:
                last_eye_value = incoming_value
                last_change_time = current_time
                if is_sleeping:
                    event_logs.append(f"[{time.strftime('%H:%M:%S')}] Eye movement detected. Exiting sleep mode.")
                    if len(event_logs) > 5: event_logs.pop(0)
                is_sleeping = False
            else:
                # 一定時間変化がないかチェック
                if current_time - last_change_time >= SLEEP_TIMEOUT:
                    if not is_sleeping:
                        event_logs.append(f"[{time.strftime('%H:%M:%S')}] No eye movement for {SLEEP_TIMEOUT}s. Entering sleep mode.")
                        if len(event_logs) > 5: event_logs.pop(0)
                    is_sleeping = True
            
            # スリープ中なら目を閉じた値に固定、そうでなければ受信した値をそのまま使用
            output_value = CLOSED_VALUE if is_sleeping else incoming_value

        # 左右の目に同じ値を送信
        left_address = address.replace("RightEyeLid", "LeftEyeLid")
        
        # 元の引数リストをコピーして、最初の値をoutput_valueに置き換える
        output_args = list(args)
        if len(output_args) > 0:
            output_args[0] = output_value
        else:
            output_args = [output_value]
            
        client.send_message(left_address, output_args)
        client.send_message(address, output_args)
        
        with state_lock:
            msg_sent_count += 2

    elif "LeftEyeLid" in address:
        # 左目のデータは右目のデータで上書きするため無視
        pass

    elif any(k in address for k in ["RightEyeX", "EyeRightX"]):
        left_address = address.replace("RightEyeX", "LeftEyeX") if "RightEyeX" in address else address.replace("EyeRightX", "EyeLeftX")
        incoming_value = args[0] if len(args) > 0 else 0.0
        with state_lock:
            last_gaze_x = incoming_value
        client.send_message(left_address, args)
        client.send_message(address, args)
        with state_lock:
            msg_sent_count += 2

    elif any(k in address for k in ["RightEyeY", "EyeRightY"]):
        left_address = address.replace("RightEyeY", "LeftEyeY") if "RightEyeY" in address else address.replace("EyeRightY", "EyeLeftY")
        incoming_value = args[0] if len(args) > 0 else 0.0
        with state_lock:
            last_gaze_y = incoming_value
        client.send_message(left_address, args)
        client.send_message(address, args)
        with state_lock:
            msg_sent_count += 2

    elif any(k in address for k in ["LeftEyeX", "LeftEyeY", "EyeLeftX", "EyeLeftY"]):
        # 左目の視線データは右目のデータで上書きするため無視
        pass

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
            f"Last Eye Move:  {time_since_change:.1f}s ago (Timeout: {SLEEP_TIMEOUT}s)\n"
        )
        
        if current_eye is not None:
            output_val = CLOSED_VALUE if current_sleep else current_eye
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