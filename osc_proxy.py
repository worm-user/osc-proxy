import threading
import time
import customtkinter as ctk
from pythonosc import dispatcher, osc_server, udp_client

from src.config_manager import load_config, state_lock
from src.osc_handler import OSCMessageHandler
from src.gui import OSCProxyGUI
from src.utils import resolve_port_conflict, monitor_steamvr, register_steamvr_manifest

# 受信ポート（Baballoniaからの送信先ポートに合わせる）
RECEIVE_PORT = 8887
# 送信ポート（VRChatまたはVRCFaceTrackingの受信ポート）
SEND_PORT = 8888
IP_ADDRESS = "127.0.0.1"

if __name__ == "__main__":
    # 1. Load config
    config = load_config()
    
    # 2. Setup OSC Client and Handler
    client = udp_client.SimpleUDPClient(IP_ADDRESS, SEND_PORT)
    disp = dispatcher.Dispatcher()
    handler = OSCMessageHandler(client, config, state_lock)
    disp.set_default_handler(handler.handle)

    # 3. Setup OSC Server
    try:
        server = osc_server.ThreadingOSCUDPServer((IP_ADDRESS, RECEIVE_PORT), disp)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or "10048" in str(e) or "Address already in use" in str(e):
            server = resolve_port_conflict(RECEIVE_PORT, disp, IP_ADDRESS)
        else:
            raise

    # 4. Start Background Threads
    monitor_thread = threading.Thread(target=monitor_steamvr, args=(server,), daemon=True)
    monitor_thread.start()

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"[{time.strftime('%H:%M:%S')}] OSC Proxy started with GUI.")
    
    # 5. Setup and Run GUI in Main Thread
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app = OSCProxyGUI(handler, config)
    
    # Log startup messages
    app.log_message(f"OSC Proxyが起動しました (受信ポート: {RECEIVE_PORT}, 送信ポート: {SEND_PORT})")
    
    # Run SteamVR auto-registration in a background thread if enabled
    def run_auto_registration():
        time.sleep(0.5) # GUIがマウントされるまでわずかに待つ
        app.log_message("SteamVR自動起動マニフェストのチェックを開始...")
        register_steamvr_manifest(app.log_message)

    if config.get("steamvr", {}).get("auto_register", True):
        reg_thread = threading.Thread(target=run_auto_registration, daemon=True)
        reg_thread.start()
    else:
        app.log_message("SteamVRへの自動起動登録は設定によりオフになっています。")
        
    app.mainloop()
    
    # 6. Shutdown
    server.shutdown()
    print("\nOSC Proxy shut down successfully.")
