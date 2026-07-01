import os
import json
import threading
import copy
from typing import Any

CONFIG_FILE: str = "config.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "network": {
        "receive_port": 8887,
        "send_port": 8888,
        "ip_address": "127.0.0.1"
    },
    "sleep_mode": {
        "enabled": True,
        "timeout_seconds": 60.0,
        "change_threshold": 0.20,
        "closed_value": 0.0,
        "enable_mouth": True
    },
    "forwarding": {
        "enable_mouth": True,
        "enable_right_eye": True,
        "enable_left_eye": True
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
        "left_gaze_y_offset": 0.0,
        "countdown_seconds": 5
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
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            
        config = copy.deepcopy(DEFAULT_CONFIG)
        if "network" in user_config:
            config["network"].update(user_config["network"])
        if "forwarding" in user_config:
            config["forwarding"].update(user_config["forwarding"])
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
        return copy.deepcopy(DEFAULT_CONFIG)

def save_config(config: dict[str, Any]) -> None:
    with state_lock:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("Config saved successfully.")
        except Exception as e:
            print(f"Error saving config: {e}")
