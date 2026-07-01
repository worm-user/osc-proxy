import threading
import time
from typing import Any
import customtkinter as ctk
from pythonosc import dispatcher, osc_server, udp_client

from src.config_manager import load_config, state_lock
from src.osc_handler import OSCMessageHandler
from src.gui import OSCProxyGUI
from src.utils import resolve_port_conflict, monitor_steamvr, register_steamvr_manifest, is_steamvr_running

if __name__ == "__main__":
    # 1. Load config
    config: dict[str, Any] = load_config()
    
    IP_ADDRESS = config.get("network", {}).get("ip_address", "127.0.0.1")
    RECEIVE_PORT = config.get("network", {}).get("receive_port", 8887)
    SEND_PORT = config.get("network", {}).get("send_port", 8888)
    
    # 2. Setup OSC Client and Handler
    client: udp_client.SimpleUDPClient = udp_client.SimpleUDPClient(IP_ADDRESS, SEND_PORT)
    disp: dispatcher.Dispatcher = dispatcher.Dispatcher()
    handler: OSCMessageHandler = OSCMessageHandler(client, config, state_lock)
    disp.set_default_handler(handler.handle)

    # 3. Setup OSC Server
    server: osc_server.ThreadingOSCUDPServer
    try:
        server = osc_server.ThreadingOSCUDPServer((IP_ADDRESS, RECEIVE_PORT), disp)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or "10048" in str(e) or "Address already in use" in str(e):
            server = resolve_port_conflict(RECEIVE_PORT, disp, IP_ADDRESS)
        else:
            raise

    # 4. Start Background Threads
    server_thread: threading.Thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"[{time.strftime('%H:%M:%S')}] OSC Proxy started with GUI.")
    
    # 5. Setup and Run GUI in Main Thread
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app: OSCProxyGUI = OSCProxyGUI(handler, config)
    
    monitor_thread: threading.Thread = threading.Thread(target=monitor_steamvr, args=(app,), daemon=True)
    monitor_thread.start()
    
    # Log startup messages
    app.log_message(f"OSC Proxyが起動しました (受信ポート: {RECEIVE_PORT}, 送信ポート: {SEND_PORT})")
    
    # Run SteamVR auto-registration in a background thread
    def run_auto_registration() -> None:
        time.sleep(0.5) # GUIがマウントされるまでわずかに待つ
        from src.utils import is_steamvr_running
        if is_steamvr_running():
            app.log_message("SteamVRの起動を検知しました。マニフェスト登録状況をチェックしています...")
            success = register_steamvr_manifest(config, app.log_message)
            if success:
                from src.config_manager import save_config
                save_config(config)
        else:
            if not config.get("steamvr", {}).get("manifest_registered", False):
                app.log_message("SteamVRが起動していません。初回起動時のマニフェスト登録を行えませんでした。")
                app.log_message("※自動起動を有効化するには、SteamVRを起動した状態で本アプリを起動するか、register.pyを実行してください。")

    reg_thread: threading.Thread = threading.Thread(target=run_auto_registration, daemon=True)
    reg_thread.start()
        
    app.mainloop()
    
    # 6. Shutdown
    from src.config_manager import save_config
    save_config(config)
    server.shutdown()
    print("\nOSC Proxy shut down successfully.")
