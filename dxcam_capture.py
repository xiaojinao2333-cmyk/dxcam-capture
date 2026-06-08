import dxcam
import time
import threading
import queue

class DXCAMCapture:
    def __init__(self, region=(0, 0, 1920, 1080), target_fps=120):
        self.region = region
        self.target_fps = target_fps
        self.camera = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.capture_thread = None
        self._running = False

    def init(self):
        if self.camera is not None:
            try:
                self.camera.stop()
            except:
                pass
        print(f"正在初始化 DXCAM... 区域: {self.region}, 目标帧率: {self.target_fps}")
        self.camera = dxcam.create(output_color="BGR")
        self.camera.start(region=self.region, target_fps=self.target_fps)
        print("DXCAM 初始化完成")
        return self

    def _capture_loop(self):
        while not self.stop_event.is_set():
            try:
                frame = self.camera.get_latest_frame()
                if frame is not None:
                    try:
                        capture_time = time.time()
                        if self.frame_queue.full():
                            self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait((frame, capture_time))
                    except Exception:
                        pass
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"DXCAM 异常: {e}")
                time.sleep(0.5)
                self.init()

    def start(self):
        if not self._running:
            self.stop_event.clear()
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            self._running = True
        return self

    def stop(self):
        if self._running:
            self.stop_event.set()
            if self.capture_thread:
                self.capture_thread.join(timeout=1)
            if self.camera:
                self.camera.stop()
            self._running = False

    def get_frame(self, timeout=0.1):
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_latest_frame(self):
        frame = None
        try:
            while not self.frame_queue.empty():
                item = self.frame_queue.get_nowait()
                if isinstance(item, tuple):
                    frame = item[0]
                else:
                    frame = item
            return frame
        except queue.Empty:
            return frame

    def is_running(self):
        return self._running

    def get_frame_with_timestamp(self):
        try:
            item = self.frame_queue.get(timeout=0.1)
            return item
        except queue.Empty:
            return None, None
