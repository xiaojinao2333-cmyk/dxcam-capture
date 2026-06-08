import cv2
import time
import threading
import dxcam


class DXCAMCapture:
    def __init__(self, region=(0, 0, 800, 600), target_fps=120):
        self.region = region
        self.target_fps = target_fps

        self.camera = None
        self.latest_frame = None
        self.latest_timestamp = 0

        self.stop_event = threading.Event()
        self.thread = None
        self.running = False

    def init(self):
        print(f"初始化 DXCAM: region={self.region}, fps={self.target_fps}")

        self.camera = dxcam.create(output_color="BGR")
        self.camera.start(region=self.region, target_fps=self.target_fps)

        return self

    def _loop(self):
        while not self.stop_event.is_set():
            frame = self.camera.get_latest_frame()
            if frame is not None:
                self.latest_frame = frame
                self.latest_timestamp = time.time()
            else:
                time.sleep(0.001)

    def start(self):
        if self.running:
            return self

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.running = True

        return self

    def get_frame(self):
        return self.latest_frame, self.latest_timestamp

    def stop(self):
        if not self.running:
            return

        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

        if self.camera:
            self.camera.stop()

        self.running = False
