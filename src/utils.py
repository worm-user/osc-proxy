import time
import os
import sys
import psutil
from pythonosc import osc_server

def resolve_port_conflict(port, disp, ip_address="127.0.0.1"):
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
                            return osc_server.ThreadingOSCUDPServer((ip_address, port), disp)
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

def register_steamvr_manifest(log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
            
    is_running = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'vrserver.exe':
                is_running = True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if not is_running:
        log("SteamVRが起動していません。自動起動登録をスキップしました。")
        return False
        
    try:
        import openvr
        manifest_path = os.path.abspath("osc_proxy.vrmanifest")
        if not os.path.exists(manifest_path):
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            manifest_path = os.path.join(base_dir, "osc_proxy.vrmanifest")
            
        if not os.path.exists(manifest_path):
            log(f"エラー: マニフェストファイル '{manifest_path}' が見つかりません。")
            return False
            
        openvr.init(openvr.VRApplication_Utility)
        
        apps = openvr.VRApplications()
        apps.addApplicationManifest(manifest_path)
        log("マニフェストの登録に成功しました！")
        
        apps.setApplicationAutoLaunch("custom.osc.eyeproxy", True)
        log("SteamVR起動時の自動実行を有効化しました。")
        
        openvr.shutdown()
        return True
    except openvr.OpenVRError as e:
        log(f"OpenVRエラー: {e}")
        return False
    except ImportError:
        log("エラー: 'openvr' パッケージがインストールされていません。")
        return False
    except Exception as e:
        log(f"登録エラー: {e}")
        return False
