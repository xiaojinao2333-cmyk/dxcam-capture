# DXCAM Screen Capture Server

高性能屏幕捕获服务，支持 HTTP 视频流输出。

## 功能特性

- 高性能屏幕捕获（支持 120 FPS）
- HTTP MJPEG 视频流
- 实时状态监控
- 低延迟输出

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python dxcam_server.py
```

## API 接口

| 接口 | 说明 |
|------|------|
| `/` | 首页，显示状态和链接 |
| `/video` | MJPEG 视频流 |
| `/single` | 单帧图片 |
| `/status` | JSON 状态信息 |
| `/config` | 获取/修改配置 |

## 配置

修改 `dxcam_server.py` 底部的默认参数：

```python
capture_region = (200, 200, 520, 520)  # 捕获区域 (x, y, width, height)
run_server(region=capture_region, target_fps=120, port=5000)
```

## 使用示例

### Python 调用
```python
import requests

# 获取单帧
resp = requests.get('http://localhost:5000/single')
with open('frame.jpg', 'wb') as f:
    f.write(resp.content)

# 获取状态
status = requests.get('http://localhost:5000/status').json()
print(status)
```

### 浏览器观看
```
http://localhost:5000/video
```

## 环境要求

- Python 3.8+
- Windows 10/11
- NVIDIA 显卡（可选，用于硬件加速）