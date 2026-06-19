import openvr
import os

# vrmanifestファイルの絶対パスを取得
manifest_path = os.path.abspath("osc_proxy.vrmanifest")

try:
    # SteamVRに接続
    openvr.init(openvr.VRApplication_Utility)
    
    # マニフェストを登録 (成功時はNoneが返り、失敗時は例外が投げられます)
    apps = openvr.VRApplications()
    apps.addApplicationManifest(manifest_path)
    
    print("マニフェストの登録に成功しました！")
    
    # ついでに自動起動（スタートアップ）もオンにしておく
    apps.setApplicationAutoLaunch("custom.osc.eyeproxy", True)
    print("SteamVR起動時の自動実行を有効化しました。")
        
    openvr.shutdown()

except openvr.OpenVRError as e:
    print(f"OpenVRエラー: {e}")
    print("※SteamVRが起動している状態でもう一度実行してください。")