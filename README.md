# OSC Proxy for Eye Tracking / VR (OSCアイプロキシ)

アイトラッキングデバイス（Baballonia等）から受信した眼球（Gaze）および眼瞼（Eyelid）のOSCパラメータを、任意の比率で合成・キャリブレーションして、VRChatやVRCFaceTrackingなどへ中継（Proxy）するためのアプリケーションです。

---

## 🌟 主な機能

### 1. 左右パラメータの任意ブレンド合成 (Mix)
* **Eyelid（まぶた）の合成:** 左右それぞれの入力値（`right_in`, `left_in`）に対して、任意のブレンド比率（0.0 〜 1.0）を設定し、左右の出力値（`right_out`, `left_out`）を動的に再生成します。
* **Gaze（視線）の合成:** 左右の視線の合成比率をスライダーで簡単に調整できます。水平方向（X）と垂直方向（Y）で同じ合成比率を共用するため、直感的かつ簡潔に調整が可能です。
* **各セクションごとのリセット機能:** Eyelid、Gazeのそれぞれに初期化（Reset）ボタンがあり、いつでもデフォルト値に戻せます。

### 2. 簡易センターキャリブレーション (Gaze Calibration)
* 「**Calibrate Center**」ボタンを押すと、3秒間のカウントダウンが始まります。
* 正面を見つめた状態でカウントダウンが終わると、その時点の左右の視線の位置を基準点（オフセット 0.0）として設定します。
* リセットボタンでキャリブレーション値を初期化（オフセットなし）することも可能です。

### 3. スマートスリープモード (Sleep Mode)
* アイトラッキングの入力（右まぶたの値）が一定時間変化しない状態（＝寝落ちやHMDの取り外しなど）を検知すると、自動的に「スリープ状態」に移行します。
* **設定可能なパラメータ:**
  * **Timeout (sec):** スリープに移行するまでの無操作時間（秒）。
  * **Change Threshold:** この値以上の変化があった場合に操作が行われたと見なす閾値。
  * **Closed Value:** スリープ移行時に出力するまぶたの値（デフォルト `0.0`：目を閉じる）。
* GUI上部のヘッダーバナーで、現在の状態（**STATUS: ACTIVE** / **STATUS: SLEEPING**）が色分けされて一目で分かります。

### 4. SteamVR連携と自動起動登録
* `register.py` を実行することで、SteamVRにマニフェストファイルを登録し、**SteamVR起動時に本アプリを自動的に起動**させることができます。
* 本アプリはSteamVRのプロセス（`vrserver.exe`）を監視しており、**SteamVRが終了すると本アプリも自動的に終了**します。

### 5. ポート競合自動解決
* 受信ポートが既に他のプロセスに占有されている場合、自動的にそれを検知します。
* 占有プロセスが以前起動していた `osc_proxy` である場合、コンソール上で古いプロセスを終了して再起動するかどうかを確認し、シームレスに移行できます。

---

## 📂 構成ファイル

```text
osc_proxy/
├── osc_proxy.py         # アプリケーションのエントリポイント
├── register.py          # SteamVRへの自動起動登録スクリプト
├── osc_proxy.vrmanifest # SteamVR自動起動用のマニフェスト
├── config.json          # 保存された設定ファイル（自動生成）
└── src/
    ├── __init__.py
    ├── config_manager.py # 設定の読み込み、保存、デフォルト値管理
    ├── osc_handler.py    # OSCメッセージ受信、ブレンド計算、スリープ、キャリブレーションの処理
    ├── gui.py            # CustomTkinterを使用したGUIレイアウトと操作
    └── utils.py          # ポート競合解決、SteamVRプロセス監視などのユーティリティ
```

---

## 🛠 導入手順

### 必要なライブラリのインストール
以下のコマンドで、必要なPythonパッケージをインストールします：

```bash
pip install customtkinter python-osc psutil openvr
```

### 実行方法

#### 1. 通常起動
```bash
python osc_proxy.py
```
GUIウィンドウが立ち上がり、デフォルトでは以下のポートでOSCの待受と転送を開始します：
* **受信ポート (Baballonia等からの送信先):** `8887`
* **送信ポート (VRChat / VRCFaceTracking等の受信ポート):** `8888`
* **IPアドレス:** `127.0.0.1`

> ※ これらのポート番号やIPアドレスは `config.json` 内の `"network"` セクションで変更可能です。

#### 2. SteamVR自動起動への登録
1. SteamVRを起動します。
2. 以下のコマンドを実行します：
   ```bash
   python register.py
   ```
3. 「マニフェストの登録に成功しました！」「SteamVR起動時の自動実行を有効化しました。」と表示されれば登録完了です。次回以降、SteamVRの起動時に自動的に本アプリが実行されます。

---

## ⚙ 設定項目の詳細

* **Eyelid / Gaze Mix:**
  * `From Right In` / `From Left In`: 入力パラメータが右目/左目の出力へどの程度反映されるかを `0.0` 〜 `1.0` で設定します。
* **Save Config to File:**
  * 設定したブレンド率、キャリブレーション値、スリープ設定を `config.json` に上書き保存します。
* **Messages / sec:**
  * 現在秒間に中継されているOSCメッセージの数を表示します。動作確認のインジケーターとして使用できます。

---

## 🚀 スタンドアロン実行ファイルのビルド

Nuitkaを使用して、Python環境がインストールされていない環境でも動作する `.exe` ファイルを作成できます。

```bash
nuitka --standalone --onefile --enable-plugin=tk-inter --windows-console-mode=disable --include-package-data=customtkinter osc_proxy.py
```
ビルド完了後、カレントディレクトリに `osc_proxy.exe` が生成されます。
