import cv2
import time
import threading
import dxcam
from flask import Flask, Response


class DXCAMCapture:
    """DXCAM 屏幕捕获模块"""
    
    def __init__(self, region=(0, 0, 800, 600), target_fps=120):
        self.region = region
        self.target_fps = target_fps

        self.camera = None
        self.latest_frame = None
        self.latest_timestamp = 0

        self.stop_event = threading.Event()
        self.thread = None
        self.running = False
        
        # 性能统计
        self.frame_count = 0
        self.last_stat_time = time.time()

    def init(self):
        """初始化 DXCAM"""
        print(f"[DXCAM] 初始化: region={self.region}, fps={self.target_fps}")
        self.camera = dxcam.create(output_color="BGR")
        self.camera.start(region=self.region, target_fps=self.target_fps)
        return self

    def _loop(self):
        """捕获循环"""
        while not self.stop_event.is_set():
            frame = self.camera.get_latest_frame()
            if frame is not None:
                self.latest_frame = frame
                self.latest_timestamp = time.time()
                self.frame_count += 1
            else:
                time.sleep(0.001)

    def start(self):
        """启动捕获"""
        if self.running:
            return self

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.running = True
        print("[DXCAM] 捕获已启动")
        return self

    def get_frame(self):
        """获取最新帧"""
        return self.latest_frame, self.latest_timestamp

    def get_stats(self):
        """获取性能统计"""
        now = time.time()
        elapsed = now - self.last_stat_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
        else:
            fps = 0
        
        # 重置计数器
        if elapsed > 1.0:
            self.frame_count = 0
            self.last_stat_time = now
            
        return {
            'fps': int(fps),
            'capture_fps': self.target_fps,
            'running': self.running
        }

    def stop(self):
        """停止捕获"""
        if not self.running:
            return

        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

        if self.camera:
            self.camera.stop()

        self.running = False
        print("[DXCAM] 捕获已停止")


# Flask 应用
app = Flask(__name__)
capture = None


def generate_mjpeg():
    """MJPEG 流生成器"""
    while True:
        try:
            if capture is not None:
                frame, ts = capture.get_frame()
                if frame is not None:
                    # 编码为 JPEG
                    ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        # 使用标准的 MJPEG 格式
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               jpg.tobytes() + b'\r\n')
            time.sleep(0.008)  # ~120fps 上限
        except Exception as e:
            print(f"[MJPEG] 生成帧异常: {e}")
            time.sleep(0.1)


@app.route('/')
def index():
    """首页"""
    stats = capture.get_stats() if capture else {}
    return f'''
    <html>
        <head>
            <title>DXCAM Server</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial; padding: 20px; }}
                h1 {{ color: #333; }}
                ul {{ line-height: 1.8; }}
                a {{ color: #0066cc; }}
                .stats {{ background: #f5f5f5; padding: 15px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <h1>📹 DXCAM Server</h1>
            <div class="stats">
                <strong>状态:</strong> {"运行中" if stats.get("running") else "已停止"}<br>
                <strong>目标帧率:</strong> {stats.get("capture_fps", 0)} FPS<br>
                <strong>当前推流:</strong> {stats.get("fps", 0)} FPS
            </div>
            <h2>可用接口:</h2>
            <ul>
                <li><a href="/video" target="_blank">📹 视频流</a></li>
                <li><a href="/single">🖼️ 单帧图片</a></li>
                <li><a href="/status">📊 状态 JSON</a></li>
            </ul>
        </body>
    </html>
    '''


@app.route('/video')
def video():
    """视频流接口"""
    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/status')
def status():
    """状态接口"""
    if capture is not None:
        stats = capture.get_stats()
        # 添加延迟信息
        frame, ts = capture.get_frame()
        if frame is not None:
            latency = (time.time() - ts) * 1000
            stats['latency_ms'] = round(latency, 1)
        return stats
    return {'status': 'stopped'}


@app.route('/single')
def single_frame():
    """单帧图片接口"""
    if capture is not None:
        frame, ts = capture.get_frame()
        if frame is not None:
            ret, jpg = cv2.imencode('.jpg', frame)
            if ret:
                return Response(jpg.tobytes(), mimetype='image/jpeg')
    return 'No frame available', 404


@app.route('/config', methods=['GET', 'POST'])
def config():
    """配置接口"""
    if capture is None:
        return {'error': 'Capture not initialized'}, 400
    
    if app.config.get('REQUEST_METHOD') == 'POST':
        # 处理配置更新
        pass
    
    # 返回当前配置
    return {
        'region': capture.region,
        'target_fps': capture.target_fps,
        'running': capture.running
    }


def run_server(region=(200, 200, 520, 520), target_fps=120, port=5000):
    """启动服务"""
    global capture
    
    print("=" * 50)
    print("正在初始化 DXCAM...")
    
    capture = DXCAMCapture(region=region, target_fps=target_fps).init().start()

    print("=" * 50)
    print("DXCAM HTTP 服务已启动！")
    print(f"  - 视频流: http://localhost:{port}/video")
    print(f"  - 状态查询: http://localhost:{port}/status")
    print(f"  - 单帧图片: http://localhost:{port}/single")
    print("  - 按 Ctrl+C 退出")
    print("=" * 50)

    app.run(host='0.0.0.0', port=port, threaded=True)


if __name__ == '__main__':
    # 默认配置
    capture_region = (200, 200, 520, 520)  # 左上角坐标, 区域大小
    run_server(region=capture_region, target_fps=120, port=5000)