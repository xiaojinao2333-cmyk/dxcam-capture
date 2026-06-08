import cv2
import time
import threading
import dxcam
from flask import Flask, Response


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


app = Flask(__name__)
capture = None


def generate():
    frame_count = 0
    boundary = "frame boundary"
    while True:
        try:
            if capture is not None:
                frame, _ = capture.get_frame()
                if frame is not None:
                    ret, jpg = cv2.imencode('.jpg', frame)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(jpg)).encode() + b'\r\n'
                               b'\r\n' + jpg.tobytes() + b'\r\n')
                        frame_count += 1
                        if frame_count % 100 == 0:
                            print(f"已发送 {frame_count} 帧")
            time.sleep(0.01)
        except Exception as e:
            print(f"生成帧异常: {e}")
            time.sleep(0.1)


@app.route('/video')
def video():
    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/status')
def status():
    if capture is not None and capture.running:
        return {'status': 'running', 'fps': capture.target_fps}
    return {'status': 'stopped'}


@app.route('/')
def index():
    return '''
    <html>
        <head><title>DXCAM Server</title></head>
        <body>
            <h1>DXCAM HTTP Server</h1>
            <ul>
                <li><a href="/video">Video Stream</a></li>
                <li><a href="/status">Status</a></li>
                <li><a href="/single">Single Frame (Debug)</a></li>
            </ul>
        </body>
    </html>
    '''


@app.route('/single')
def single_frame():
    if capture is not None:
        frame, ts = capture.get_frame()
        if frame is not None:
            ret, jpg = cv2.imencode('.jpg', frame)
            if ret:
                return Response(jpg.tobytes(), mimetype='image/jpeg')
    return 'No frame available', 404


if __name__ == '__main__':
    capture_region = (200, 200, 520, 520)

    print("正在初始化 DXCAM...")
    capture = DXCAMCapture(region=capture_region, target_fps=120).init().start()

    print("=" * 50)
    print("DXCAM HTTP 服务已启动！")
    print("视频流: http://localhost:5000/video")
    print("状态查询: http://localhost:5000/status")
    print("按 Ctrl+C 退出")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, threaded=True)
