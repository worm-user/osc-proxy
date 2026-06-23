import os
import json
import threading
from typing import Any

CONFIG_FILE: str = "config.json"
DEFAULT_CONFIG: dict[str, Any] = {
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
        "gaze": {
            "right_out": { "right_in": 1.0, "left_in": 0.0 },
            "left_out":  { "right_in": 1.0, "left_in": 0.0 }
        }
    },
    "calibration": {
        "right_gaze_x_offset": 0.0,
        "left_gaze_x_offset": 0.0,
        "right_gaze_y_offset": 0.0,
        "left_gaze_y_offset": 0.0
    },
    "steamvr": {
        "auto_launch": True,
        "manifest_registered": False
    }
}

# 状態管理用ロック (GUIとOSCハンドラ間で共有)
state_lock: threading.Lock = threading.Lock()

def load_config() -> dict[str, Any]:
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
            if "gaze_x" in user_config["mix"] and "gaze" not in user_config["mix"]:
                config["mix"]["gaze"] = user_config["mix"]["gaze_x"]
            config["mix"].update(user_config["mix"])
            config["mix"].pop("gaze_x", None)
            config["mix"].pop("gaze_y", None)
        if "calibration" in user_config:
            config["calibration"].update(user_config["calibration"])
        if "steamvr" in user_config:
            if "auto_register" in user_config["steamvr"]:
                user_config["steamvr"]["auto_launch"] = user_config["steamvr"].pop("auto_register")
            config["steamvr"].update(user_config["steamvr"])
        return config
    except Exception as e:
        print(f"Error reading config.json: {e}. Using default settings.")
        return DEFAULT_CONFIG

def save_config(config: dict[str, Any]) -> None:
    with state_lock:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("Config saved successfully.")
        except Exception as e:
            print(f"Error saving config: {e}")
