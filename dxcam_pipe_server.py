import time
import threading
import struct
import dxcam
import win32pipe
import win32file


class DXCAMPipeServer:
    """DXCAM Named Pipe 服务"""
    
    def __init__(self, region=(200, 200, 520, 520), target_fps=120):
        self.region = region
        self.target_fps = target_fps
        
        self.camera = None
        self.latest_frame = None
        self.latest_timestamp = 0
        
        self.running = False
        self.capture_thread = None
        self.stop_event = threading.Event()
        
        # 统计信息
        self.frame_count = 0

    def init(self):
        """初始化 DXCAM"""
        print(f"[DXCAM] 初始化: region={self.region}, fps={self.target_fps}")
        self.camera = dxcam.create(output_color="BGR")
        self.camera.start(region=self.region, target_fps=self.target_fps)
        return self

    def capture_loop(self):
        """捕获循环"""
        while not self.stop_event.is_set():
            frame = self.camera.get_latest_frame()
            if frame is not None:
                self.latest_frame = frame
                self.latest_timestamp = time.time()
                self.frame_count += 1
            else:
                time.sleep(0.001)

    def run(self):
        """运行服务"""
        pipe_name = r'\\.\pipe\dxcam_capture'
        print(f"[PIPE] 服务已启动: {pipe_name}")
        
        while not self.stop_event.is_set():
            pipe_handle = None
            try:
                # 创建管道（支持 10 个实例）
                pipe_handle = win32pipe.CreateNamedPipe(
                    pipe_name,
                    win32pipe.PIPE_ACCESS_OUTBOUND,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_WAIT,
                    10,  # 最大实例数
                    1024 * 1024,  # 输出缓冲区 1MB
                    1024 * 1024,  # 输入缓冲区 1MB
                    1000,  # 超时 1s
                    None
                )
                
                # 等待连接
                print(f"[PIPE] 等待客户端连接...")
                try:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                    print("[PIPE] 客户端已连接")
                except Exception:
                    continue
                
                # 发送帧循环
                last_stat = time.time()
                while not self.stop_event.is_set():
                    frame, ts = self.get_frame()
                    if frame is not None:
                        # 发送帧头
                        height, width = frame.shape[:2]
                        header = struct.pack('<III', width, height, 3)
                        win32file.WriteFile(pipe_handle, header)
                        
                        # 发送帧数据
                        data = frame.tobytes()
                        win32file.WriteFile(pipe_handle, data)
                    else:
                        time.sleep(0.001)
                    
                    # 统计信息
                    now = time.time()
                    if now - last_stat > 1:
                        print(f"[PIPE] 已发送 {self.frame_count} 帧")
                        self.frame_count = 0
                        last_stat = now
                
            except Exception as e:
                pass
                
            finally:
                # 清理
                if pipe_handle:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except:
                        pass
                print("[PIPE] 连接已断开")

    def start(self):
        """启动服务"""
        if self.running:
            return self
        
        self.running = True
        self.stop_event.clear()
        
        # 启动捕获线程
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()
        print("[DXCAM] 捕获已启动")
        
        # 在主线程运行管道服务
        self.run()
        
        return self

    def get_frame(self):
        """获取最新帧"""
        return self.latest_frame, self.latest_timestamp

    def stop(self):
        """停止服务"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.capture_thread:
            self.capture_thread.join(timeout=1)
        
        if self.camera:
            self.camera.stop()
        
        print("[DXCAM] 已停止")


if __name__ == '__main__':
    capture_region = (200, 200, 520, 520)
    
    print("=" * 50)
    print("DXCAM Named Pipe 服务")
    print("=" * 50)
    print("管道地址: \\\\.\\pipe\\dxcam_capture")
    print("按 Ctrl+C 退出")
    print("=" * 50)
    
    server = DXCAMPipeServer(region=capture_region, target_fps=120).init()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n正在关闭...")
        server.stop()