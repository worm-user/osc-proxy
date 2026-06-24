import time
from typing import Any, Optional, Tuple
from threading import Lock
from pythonosc.udp_client import SimpleUDPClient

class OSCMessageHandler:
    client: SimpleUDPClient
    config: dict[str, Any]
    lock: Lock
    
    last_eye_value: Optional[float]
    last_change_time: float
    is_sleeping: bool
    msg_sent_count: int
    
    in_right_lid: float
    in_left_lid: float
    
    raw_right_gaze_x: float
    raw_left_gaze_x: float
    raw_right_gaze_y: float
    raw_left_gaze_y: float

    last_right_lid_address: str
    last_left_lid_address: str

    def __init__(self, client: SimpleUDPClient, config: dict[str, Any], lock: Lock) -> None:
        self.client = client
        self.config = config
        self.lock = lock
        
        self.last_eye_value = None
        self.last_change_time = time.time()
        self.is_sleeping = False
        self.msg_sent_count = 0
        
        self.in_right_lid = 0.0
        self.in_left_lid = 0.0
        
        self.raw_right_gaze_x = 0.0
        self.raw_left_gaze_x = 0.0
        self.raw_right_gaze_y = 0.0
        self.raw_left_gaze_y = 0.0

        self.last_right_lid_address = "/avatar/parameters/RightEyeLid"
        self.last_left_lid_address = "/avatar/parameters/LeftEyeLid"

    def get_status(self) -> Tuple[int, bool]:
        current_time = time.time()
        with self.lock:
            if self.config["sleep_mode"]["enabled"]:
                if not self.is_sleeping:
                    if current_time - self.last_change_time >= self.config["sleep_mode"]["timeout_seconds"]:
                        self.is_sleeping = True
                        closed_val = self.config["sleep_mode"]["closed_value"]
                        self.client.send_message(self.last_right_lid_address, [closed_val])
                        self.client.send_message(self.last_left_lid_address, [closed_val])
            else:
                if self.is_sleeping:
                    self.is_sleeping = False
            
            count = self.msg_sent_count
            self.msg_sent_count = 0
            is_sleeping = self.is_sleeping
        return count, is_sleeping

    def get_raw_gaze(self) -> Tuple[float, float, float, float]:
        with self.lock:
            return self.raw_right_gaze_x, self.raw_left_gaze_x, self.raw_right_gaze_y, self.raw_left_gaze_y

    def handle(self, address: str, *args: Any) -> None:
        incoming_value: float = args[0] if len(args) > 0 else 0.0
        current_time: float = time.time()

        if "RightEyeLid" in address or "LeftEyeLid" in address:
            self._handle_eyelid(address, incoming_value, current_time, args)
        elif any(k in address for k in ["RightEyeX", "EyeRightX", "LeftEyeX", "EyeLeftX"]):
            self._handle_gaze_x(address, incoming_value, args)
        elif any(k in address for k in ["RightEyeY", "EyeRightY", "LeftEyeY", "EyeLeftY"]):
            self._handle_gaze_y(address, incoming_value, args)
        else:
            self._handle_default(address, args)

    def _handle_eyelid(self, address: str, incoming_value: float, current_time: float, args: Tuple[Any, ...]) -> None:
        with self.lock:
            if "RightEyeLid" in address:
                self.last_right_lid_address = address
                self.in_right_lid = incoming_value
                self._update_sleep_state(incoming_value, current_time)
            else:
                self.last_left_lid_address = address
                self.in_left_lid = incoming_value
            
            mix_cfg = self.config["mix"]["eyelid"]
            out_right = self.in_right_lid * mix_cfg["right_out"]["right_in"] + self.in_left_lid * mix_cfg["right_out"]["left_in"]
            out_left  = self.in_right_lid * mix_cfg["left_out"]["right_in"]  + self.in_left_lid * mix_cfg["left_out"]["left_in"]
            
            if self.config["sleep_mode"]["enabled"] and self.is_sleeping:
                out_right = self.config["sleep_mode"]["closed_value"]
                out_left = self.config["sleep_mode"]["closed_value"]

        self._send_mixed_messages(address, "RightEyeLid", "LeftEyeLid", out_right, out_left, args)

    def _update_sleep_state(self, incoming_value: float, current_time: float) -> None:
        if self.config["sleep_mode"]["enabled"]:
            if self.last_eye_value is None or abs(incoming_value - self.last_eye_value) >= self.config["sleep_mode"]["change_threshold"]:
                self.last_eye_value = incoming_value
                self.last_change_time = current_time
                self.is_sleeping = False
            else:
                if current_time - self.last_change_time >= self.config["sleep_mode"]["timeout_seconds"]:
                    self.is_sleeping = True
        else:
            self.last_eye_value = incoming_value
            self.is_sleeping = False

    def _handle_gaze_x(self, address: str, incoming_value: float, args: Tuple[Any, ...]) -> None:
        is_right = "RightEyeX" in address or "EyeRightX" in address
        with self.lock:
            if is_right:
                self.raw_right_gaze_x = incoming_value
            else:
                self.raw_left_gaze_x = incoming_value
                
            calib_rx = self.raw_right_gaze_x - self.config["calibration"]["right_gaze_x_offset"]
            calib_lx = self.raw_left_gaze_x - self.config["calibration"]["left_gaze_x_offset"]
            
            mix_cfg = self.config["mix"]["gaze"]
            out_right = calib_rx * mix_cfg["right_out"]["right_in"] + calib_lx * mix_cfg["right_out"]["left_in"]
            out_left  = calib_rx * mix_cfg["left_out"]["right_in"]  + calib_lx * mix_cfg["left_out"]["left_in"]

        self._send_gaze_messages(address, is_right, "EyeX", out_right, out_left, args)

    def _handle_gaze_y(self, address: str, incoming_value: float, args: Tuple[Any, ...]) -> None:
        is_right = "RightEyeY" in address or "EyeRightY" in address
        with self.lock:
            if is_right:
                self.raw_right_gaze_y = incoming_value
            else:
                self.raw_left_gaze_y = incoming_value
                
            calib_ry = self.raw_right_gaze_y - self.config["calibration"]["right_gaze_y_offset"]
            calib_ly = self.raw_left_gaze_y - self.config["calibration"]["left_gaze_y_offset"]
            
            mix_cfg = self.config["mix"]["gaze"]
            out_right = calib_ry * mix_cfg["right_out"]["right_in"] + calib_ly * mix_cfg["right_out"]["left_in"]
            out_left  = calib_ry * mix_cfg["left_out"]["right_in"]  + calib_ly * mix_cfg["left_out"]["left_in"]

        self._send_gaze_messages(address, is_right, "EyeY", out_right, out_left, args)

    def _send_gaze_messages(self, address: str, is_right: bool, axis_suffix: str, out_right: float, out_left: float, args: Tuple[Any, ...]) -> None:
        if axis_suffix == "EyeX":
            right_keys = ["RightEyeX", "EyeRightX"]
            left_keys = ["LeftEyeX", "EyeLeftX"]
        else:
            right_keys = ["RightEyeY", "EyeRightY"]
            left_keys = ["LeftEyeY", "EyeLeftY"]
            
        r_addr = address
        l_addr = address
        
        if is_right:
            for r_key, l_key in zip(right_keys, left_keys):
                if r_key in address:
                    l_addr = address.replace(r_key, l_key)
                    break
        else:
            for l_key, r_key in zip(left_keys, right_keys):
                if l_key in address:
                    r_addr = address.replace(l_key, r_key)
                    break

        self._send_mixed_messages(None, None, None, out_right, out_left, args, r_addr=r_addr, l_addr=l_addr)

    def _send_mixed_messages(self, address: Optional[str], right_key: Optional[str], left_key: Optional[str], out_right: float, out_left: float, args: Tuple[Any, ...], r_addr: Optional[str] = None, l_addr: Optional[str] = None) -> None:
        if r_addr is None or l_addr is None:
            if address is not None and right_key is not None and left_key is not None:
                if right_key in address:
                    r_addr = address
                    l_addr = address.replace(right_key, left_key)
                else:
                    l_addr = address
                    r_addr = address.replace(left_key, right_key)
            else:
                return

        out_r = list(args)
        if len(out_r) > 0: out_r[0] = out_right
        else: out_r = [out_right]
        
        out_l = list(args)
        if len(out_l) > 0: out_l[0] = out_left
        else: out_l = [out_left]
        
        self.client.send_message(r_addr, out_r)
        self.client.send_message(l_addr, out_l)
        
        with self.lock:
            self.msg_sent_count += 2

    def _handle_default(self, address: str, args: Tuple[Any, ...]) -> None:
        self.client.send_message(address, args)
        with self.lock:
            self.msg_sent_count += 1
