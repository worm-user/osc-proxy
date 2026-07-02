# OSC Proxy for Eye Tracking / VR

アイトラッキングデバイス等から受信したOSCパラメータを合成・調整し、VRChat等へ中継するアプリケーションです。

## 主な機能

1. パラメータのブレンド合成
   - まぶた (Eyelid) と視線 (Gaze) の左右入力値を任意の比率で合成して出力します。
2. センターキャリブレーション
   - 現在の視線位置を基準点(オフセット0)として設定します。
3. スリープモード
   - 一定時間まぶたの動きがない場合、自動で目を閉じた状態(および口を閉じた状態)に固定します。
4. SteamVR連携
   - SteamVR起動時に自動起動し、SteamVR終了時に自動終了します。
5. ログ出力と自動保存
   - 動作ログは `logs/` フォルダ内に日別で保存されます。終了時に設定は自動保存されます。

## 構成ファイル

```text
osc_proxy/
├── osc_proxy.py         # アプリケーションのエントリポイント
├── register.py          # SteamVRへの自動起動登録スクリプト
├── osc_proxy.vrmanifest # SteamVR自動起動用のマニフェスト
├── config.json          # 保存された設定ファイル（自動生成）
├── logs/                # 動作ログ出力フォルダ
└── src/                 # ソースコードディレクトリ
```

## 導入と実行

### 必要環境
以下のコマンドで必要なPythonパッケージをインストールします。

```bash
pip install customtkinter python-osc psutil openvr
```

### 起動
```bash
python osc_proxy.py
```
デフォルトのポート設定:
* 受信ポート: 8887
* 送信ポート: 8888
* IPアドレス: 127.0.0.1
※ 設定は `config.json` の `network` セクションから変更可能です。

### SteamVR自動起動の設定
SteamVRを起動した状態で以下のコマンドを実行してください。

```bash
python register.py
```

## 実行ファイルのビルド

Nuitkaを使用してスタンドアロンな `.exe` ファイルを作成できます。

```bash
nuitka --standalone --onefile --enable-plugin=tk-inter --windows-console-mode=disable --include-package-data=customtkinter osc_proxy.py
```
