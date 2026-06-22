import sys
from src.utils import register_steamvr_manifest

if __name__ == "__main__":
    print("SteamVRへの自動起動登録を実行中...")
    success = register_steamvr_manifest(print)
    if not success:
        print("\n※SteamVRが起動している状態でもう一度実行してください。")
        sys.exit(1)