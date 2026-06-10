import cv2
import time
import struct
import win32file
import win32pipe


class DXCAMPipeClient:
    """DXCAM Named Pipe 客户端"""
    
    def __init__(self, pipe_name=r'\\.\pipe\dxcam_capture'):
        self.pipe_name = pipe_name
        self.pipe_handle = None
        self.connected = False

    def connect(self):
        """连接到管道"""
        print(f"[CLIENT] 正在连接 {self.pipe_name}...")
        
        try:
            self.pipe_handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            self.connected = True
            print("[CLIENT] 已连接")
            return True
        except Exception as e:
            print(f"[CLIENT] 连接失败: {e}")
            return False

    def read_frame(self):
        """读取一帧"""
        if not self.connected or self.pipe_handle is None:
            return None
        
        try:
            # 读取帧头 (width, height, channels)
            header = win32file.ReadFile(self.pipe_handle, 12)[1]
            width, height, channels = struct.unpack('<III', header)
            
            # 读取帧数据
            data = win32file.ReadFile(self.pipe_handle, width * height * channels)[1]
            
            # 重建 numpy 数组
            import numpy as np
            frame = np.frombuffer(data, dtype=np.uint8).copy()  # copy 使其可写
            frame = frame.reshape((height, width, channels))
            
            return frame
        except Exception as e:
            print(f"[CLIENT] 读取失败: {e}")
            self.connected = False
            return None

    def close(self):
        """关闭连接"""
        if self.pipe_handle is not None:
            win32file.CloseHandle(self.pipe_handle)
            self.pipe_handle = None
            self.connected = False


if __name__ == '__main__':
    import numpy as np
    
    client = DXCAMPipeClient()
    
    if client.connect():
        print("=" * 50)
        print("测试 Named Pipe 延迟")
        print("按 'q' 退出")
        print("=" * 50)
        
        # FPS 和延迟统计
        frame_times = []
        last_print = time.time()
        
        try:
            while True:
                # 读取帧
                start_read = time.time()
                frame = client.read_frame()
                if frame is None:
                    # 尝试重连
                    time.sleep(0.5)
                    client.close()
                    client.connect()
                    continue
                
                # 显示帧
                latency = (time.time() - start_read) * 1000
                frame_times.append(latency)
                
                # 显示在画面上
                cv2.putText(frame, f"Latency: {latency:.1f}ms", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # 每 0.5 秒打印统计
                now = time.time()
                if now - last_print > 0.5:
                    avg_latency = sum(frame_times[-50:]) / min(50, len(frame_times))
                    fps = int(1000 / avg_latency) if avg_latency > 0 else 0
                    print(f"FPS: {fps} | Latency: {avg_latency:.1f}ms")
                    last_print = now
                
                cv2.imshow("DXCAM Pipe", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except KeyboardInterrupt:
            pass
        finally:
            client.close()
            cv2.destroyAllWindows()