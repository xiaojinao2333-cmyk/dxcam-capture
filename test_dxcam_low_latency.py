import cv2
import time
from collections import deque
from dxcam_low_latency import DXCAMCapture

capture_region = (200, 200, 520, 520)

print("正在初始化 DXCAM...")
capture = DXCAMCapture(region=capture_region, target_fps=120).init().start()

print("按 q 退出")

frame_times = deque(maxlen=30)
last_print = time.time()

fps_counter = 0
fps = 0

try:
    while True:
        frame, ts = capture.get_frame()

        if frame is not None:
            now = time.time()

            latency = (now - ts) * 1000
            frame_times.append(latency)

            fps_counter += 1

            if now - last_print >= 0.2:
                avg_latency = sum(frame_times) / len(frame_times) if frame_times else 0
                fps = int(fps_counter / (now - last_print))

                print(f"FPS: {fps} | 平均延迟: {avg_latency:.2f}ms | 当前延迟: {latency:.2f}ms")

                fps_counter = 0
                last_print = now
                frame_times.clear()

            vis = frame.copy()

            cv2.putText(vis, f"FPS: {fps}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.putText(vis, f"Latency: {latency:.1f} ms", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            cv2.imshow("DXCAM Low Latency", vis)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    capture.stop()
    cv2.destroyAllWindows()
    print("已退出")
