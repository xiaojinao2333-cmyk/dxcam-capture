import cv2
import numpy as np
from ultralytics import YOLO
import time
import queue
from collections import defaultdict, deque
from rsr_ch9329 import create_mouse
from dxcam_server import DXCAMCapture

PREDICTION_FRAMES = 8

print("正在加载 YOLO26s 模型...")

try:
    ov_model = YOLO("yolo26s_int8_openvino_model/", task='detect')
except:
    model = YOLO("yolo26s.pt")
    model.export(format="openvino", imgsz=320, int8=True)
    ov_model = YOLO("yolo26s_int8_openvino_model/", task='detect')

print("正在预热模型...")
dummy_frame = np.zeros((320, 320, 3), dtype=np.uint8)
_ = ov_model.predict(dummy_frame, device='cpu', verbose=False)
print("模型预热完成")

capture_region = (200, 200, 520, 520)
frame_queue = queue.Queue(maxsize=2)
result_queue = queue.Queue(maxsize=2)
stop_event = __import__('threading').Event()

trajectory_history = defaultdict(lambda: deque(maxlen=20))
trajectory_lock = __import__('threading').Lock()

class TrajectoryPredictor:
    def __init__(self, history_len=20, predict_frames=8):
        self.history_len = history_len
        self.predict_frames = predict_frames

    def update(self, track_id, x, y, timestamp):
        with trajectory_lock:
            self.history = trajectory_history[track_id]
            self.history.append((x, y, timestamp))

    def predict(self, track_id):
        with trajectory_lock:
            history = trajectory_history.get(track_id)
            if history is None or len(history) < 2:
                return None

            positions = [(h[0], h[1]) for h in history]

            n = len(positions)

            sum_x = sum(p[0] for p in positions)
            sum_y = sum(p[1] for p in positions)
            sum_t = sum(i for i in range(n))
            sum_tx = sum(i * positions[i][0] for i in range(n))
            sum_ty = sum(i * positions[i][1] for i in range(n))
            sum_t2 = sum(i * i for i in range(n))

            denom = n * sum_t2 - sum_t * sum_t
            if abs(denom) < 1e-6:
                vx = positions[-1][0] - positions[-2][0]
                vy = positions[-1][1] - positions[-2][1]
            else:
                vx = (n * sum_tx - sum_t * sum_x) / denom
                vy = (n * sum_ty - sum_t * sum_y) / denom

            last_x = positions[-1][0]
            last_y = positions[-1][1]

            pred_x = last_x + vx * self.predict_frames
            pred_y = last_y + vy * self.predict_frames

            return int(pred_x), int(pred_y), vx, vy

predictor = TrajectoryPredictor(history_len=20, predict_frames=PREDICTION_FRAMES)

capture = DXCAMCapture(region=capture_region, target_fps=120).init().start()

def inference_thread():
    while not stop_event.is_set():
        frame, capture_ts = capture.get_frame()
        if frame is None:
            time.sleep(0.001)
            continue

        infer_start_time = time.time()
        capture_delay = (infer_start_time - capture_ts) * 1000

        results = ov_model.track(
            frame,
            persist=True,
            tracker="bytetrack_optimized.yaml",
            imgsz=320,
            classes=[0],
            conf=0.6,
            verbose=False,
            device='cpu'
        )

        infer_end_time = time.time()
        infer_latency = (infer_end_time - infer_start_time) * 1000
        total_latency = (infer_end_time - capture_ts) * 1000

        if result_queue.full():
            try:
                result_queue.get_nowait()
            except queue.Empty:
                pass

        result_queue.put((frame, results, capture_delay, infer_latency, total_latency, infer_end_time))

inf_thread = __import__('threading').Thread(target=inference_thread, daemon=True)
inf_thread.start()

print("正在初始化 CH9329 鼠标...")
try:
    mouse = create_mouse()
except Exception as e:
    print(f"CH9329 鼠标初始化失败，继续只测试链路延迟: {e}")
    mouse = None

print("按 'q' 键退出...")
prev_time = time.time()

try:
    while True:
        try:
            frame, results, capture_delay, infer_latency, total_latency, infer_ts = result_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        render_latency = (time.time() - infer_ts) * 1000
        chain_latency = total_latency + render_latency

        annotated_frame = frame.copy()
        timestamp = time.time()

        best_box = None
        best_conf = 0

        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf = float(box.conf[0].cpu().numpy())
                    if conf > best_conf:
                        best_conf = conf
                        best_box = box

        if best_box is not None:
            x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy().astype(int)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            if best_box.id is not None:
                track_id = int(best_box.id[0].cpu().numpy())

                predictor.update(track_id, cx, cy, timestamp)
                prediction = predictor.predict(track_id)

                if prediction:
                    pred_x, pred_y, vx, vy = prediction

                    if mouse:
                        screen_x = capture_region[0] + pred_x
                        screen_y = capture_region[1] + pred_y
                        mouse.move_to(screen_x, screen_y)

                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated_frame, f"ID:{track_id}", (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    cv2.circle(annotated_frame, (cx, cy), 5, (0, 255, 0), -1)

                    cv2.circle(annotated_frame, (pred_x, pred_y), 5, (0, 0, 255), -1)
                    cv2.line(annotated_frame, (cx, cy), (pred_x, pred_y), (0, 0, 255), 2)
                    cv2.putText(annotated_frame, f"P({pred_x},{pred_y})", (pred_x+10, pred_y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                    cv2.putText(annotated_frame, f"v({vx:.1f},{vy:.1f})", (x1, y2+15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                else:
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated_frame, f"ID:{track_id}", (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.circle(annotated_frame, (cx, cy), 5, (0, 255, 0), -1)
            else:
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(annotated_frame, (cx, cy), 5, (0, 255, 0), -1)

        curr_time = time.time()
        real_fps = 1 / (curr_time - prev_time)
        prev_time = curr_time

        cv2.putText(annotated_frame, f"FPS: {int(real_fps)}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Capture: {capture_delay:.1f}ms", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated_frame, f"Infer: {infer_latency:.1f}ms", (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated_frame, f"RenderQ: {render_latency:.1f}ms", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(annotated_frame, f"Chain: {chain_latency:.1f}ms", (20, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("YOLO26s DXCAM Chain Latency", annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

finally:
    stop_event.set()
    capture.stop()
    inf_thread.join(timeout=1)
    if mouse and mouse.ser:
        mouse.disconnect()
    cv2.destroyAllWindows()
    print("程序已退出")
