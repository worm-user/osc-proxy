import time
import threading
from typing import Any, Optional, Tuple, Dict, List
from threading import Lock
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_bundle_builder import OscBundleBuilder
from pythonosc.osc_message_builder import OscMessageBuilder

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
    
    pending_messages: dict[str, list[Any]]

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
        self.sleep_last_send_times: dict[str, float] = {}
        self.pending_messages = {}
        
        self.bundle_thread = threading.Thread(target=self._bundle_sender_loop, daemon=True)
        self.bundle_thread.start()

    def _bundle_sender_loop(self) -> None:
        while True:
            time.sleep(0.016)  # ~60Hz
            with self.lock:
                if not self.pending_messages:
                    continue
                msgs_to_send = self.pending_messages.copy()
                self.pending_messages.clear()
            
            bundle_builder = OscBundleBuilder(0)
            sent_count = 0
            
            for addr, args in msgs_to_send.items():
                msg_builder = OscMessageBuilder(address=addr)
                for arg in args:
                    msg_builder.add_arg(arg)
                bundle_builder.add_content(msg_builder.build())
                sent_count += 1
                
            bundle = bundle_builder.build()
            try:
                self.client.send(bundle)
                with self.lock:
                    self.msg_sent_count += sent_count
            except Exception:
                pass

    def get_status(self) -> Tuple[int, bool]:
        current_time = time.time()
        with self.lock:
            if self.config["sleep_mode"]["enabled"]:
                if not self.is_sleeping:
                    if current_time - self.last_change_time >= self.config["sleep_mode"]["timeout_seconds"]:
                        self.is_sleeping = True
                        self.sleep_last_send_times.clear()
                        closed_val = self.config["sleep_mode"]["closed_value"]
                        self.pending_messages[self.last_right_lid_address] = [closed_val]
                        self.pending_messages[self.last_left_lid_address] = [closed_val]
            else:
                if self.is_sleeping:
                    self.is_sleeping = False
                    self.sleep_last_send_times.clear()
            
            count = self.msg_sent_count
            self.msg_sent_count = 0
            is_sleeping = self.is_sleeping
        return count, is_sleeping

    def get_raw_gaze(self) -> Tuple[float, float, float, float]:
        with self.lock:
            return self.raw_right_gaze_x, self.raw_left_gaze_x, self.raw_right_gaze_y, self.raw_left_gaze_y

    def _check_rate_limit(self, address: str, current_time: float) -> bool:
        """Returns True if the message should be DROPPED to maintain a staggered 1 msg/s rate."""
        if address not in self.sleep_last_send_times:
            # Assign a deterministic random offset based on the address to stagger the sending
            h = abs(hash(address))
            offset = (h % 1000) / 1000.0  # 0.0 ~ 0.999
            self.sleep_last_send_times[address] = current_time - 1.0 + offset
            return True  # Drop the first frame to enforce the offset

        last_time = self.sleep_last_send_times[address]
        if current_time - last_time < 1.0:
            return True  # Drop

        self.sleep_last_send_times[address] = current_time
        return False  # Pass

    def handle(self, address: str, *args: Any) -> None:
        incoming_value: float = args[0] if len(args) > 0 else 0.0
        current_time: float = time.time()

        if "RightEyeLid" in address or "LeftEyeLid" in address:
            self._handle_eyelid(address, incoming_value, current_time, args)
        elif any(k in address for k in ["RightEyeX", "EyeRightX", "LeftEyeX", "EyeLeftX"]):
            self._handle_gaze_x(address, incoming_value, current_time, args)
        elif any(k in address for k in ["RightEyeY", "EyeRightY", "LeftEyeY", "EyeLeftY"]):
            self._handle_gaze_y(address, incoming_value, current_time, args)
        else:
            self._handle_default(address, current_time, args)

    def _handle_eyelid(self, address: str, incoming_value: float, current_time: float, args: Tuple[Any, ...]) -> None:
        with self.lock:
            if "RightEyeLid" in address:
                self.last_right_lid_address = address
                self.in_right_lid = incoming_value
                self._update_sleep_state(incoming_value, current_time)
            else:
                self.last_left_lid_address = address
                self.in_left_lid = incoming_value
            
            if self.is_sleeping:
                if self._check_rate_limit(address, current_time):
                    return
            
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
                if self.is_sleeping:
                    self.is_sleeping = False
                    self.sleep_last_send_times.clear()
            else:
                if not self.is_sleeping and current_time - self.last_change_time >= self.config["sleep_mode"]["timeout_seconds"]:
                    self.is_sleeping = True
                    self.sleep_last_send_times.clear()
                    closed_val = self.config["sleep_mode"]["closed_value"]
                    self.pending_messages[self.last_right_lid_address] = [closed_val]
                    self.pending_messages[self.last_left_lid_address] = [closed_val]
        else:
            self.last_eye_value = incoming_value
            if self.is_sleeping:
                self.is_sleeping = False
                self.sleep_last_send_times.clear()

    def _handle_gaze_x(self, address: str, incoming_value: float, current_time: float, args: Tuple[Any, ...]) -> None:
        is_right = "RightEyeX" in address or "EyeRightX" in address
        with self.lock:
            if self.is_sleeping:
                if self._check_rate_limit(address, current_time):
                    return

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

    def _handle_gaze_y(self, address: str, incoming_value: float, current_time: float, args: Tuple[Any, ...]) -> None:
        is_right = "RightEyeY" in address or "EyeRightY" in address
        with self.lock:
            if self.is_sleeping:
                if self._check_rate_limit(address, current_time):
                    return

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
        
        with self.lock:
            do_right = self.config["forwarding"]["enable_right_eye"]
            do_left = self.config["forwarding"]["enable_left_eye"]
            
            if do_right:
                self.pending_messages[r_addr] = out_r
            if do_left:
                self.pending_messages[l_addr] = out_l

    def _is_mouth_parameter(self, address: str) -> bool:
        if not hasattr(self, "mouth_params"):
            try:
                import os
                if os.path.exists("mouth_params_list.txt"):
                    with open("mouth_params_list.txt", "r", encoding="utf-8") as f:
                        self.mouth_params = [line.strip().lower() for line in f if line.strip()]
                else:
                    self.mouth_params = ["mouth", "jaw", "cheek", "tongue", "nose"]
            except Exception:
                self.mouth_params = ["mouth", "jaw", "cheek", "tongue", "nose"]
        addr_lower = address.lower()
        return any(k in addr_lower for k in self.mouth_params)

    def _handle_default(self, address: str, current_time: float, args: Tuple[Any, ...]) -> None:
        if self._is_mouth_parameter(address):
            with self.lock:
                if not self.config["forwarding"]["enable_mouth"]:
                    return
                if self.is_sleeping:
                    if not self.config["sleep_mode"]["enable_mouth"]:
                        return
                    if self._check_rate_limit(address, current_time):
                        return

        with self.lock:
            self.pending_messages[address] = list(args)
