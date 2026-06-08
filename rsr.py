import serial
import time

SERIAL_PORT = "COM11"   # Windows: COM3 / Linux: /dev/ttyUSB0
BAUDRATE = 115200


# =============================
# 🧠 构建数据包（自动校验）
# =============================
def build_packet(data_bytes):
    packet = [0x57, 0xAB, 0x00, 0x04, 0x07] + data_bytes
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    return bytes(packet)


# =============================
# 📐 屏幕坐标 → 芯片4096坐标
# =============================
def convert_to_4096(x, y, screen_w, screen_h):
    x_4096 = int(x * 4096 / screen_w)
    y_4096 = int(y * 4096 / screen_h)

    # 防越界
    x_4096 = max(0, min(4095, x_4096))
    y_4096 = max(0, min(4095, y_4096))

    return x_4096, y_4096


# =============================
# 🖱 绝对移动
# =============================
def move_abs(ser, x, y, screen_w, screen_h):
    x_4096, y_4096 = convert_to_4096(x, y, screen_w, screen_h)

    x_low  = x_4096 & 0xFF
    x_high = (x_4096 >> 8) & 0xFF
    y_low  = y_4096 & 0xFF
    y_high = (y_4096 >> 8) & 0xFF

    data = [0x02, 0x00, x_low, x_high, y_low, y_high, 0x00]
    packet = build_packet(data)

    ser.write(packet)

    # 可选：读返回
    resp = ser.read(7)
    print("发送:", packet.hex(" "))
    print("返回:", resp.hex(" "))


# =============================
# 🧪 测试
# =============================
if __name__ == "__main__":
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except serial.SerialException as e:
        print(f"❌ 无法打开串口 {SERIAL_PORT}")
        print(f"   请检查：")
        print(f"   1. 串口设备是否已插入")
        print(f"   2. 串口是否为 {SERIAL_PORT}")
        print(f"   3. 驱动程序是否正常")
        print(f"\n错误信息: {e}")
        import sys
        sys.exit(0)

    time.sleep(1)

    screen_w = 1920
    screen_h = 1080

    # 🎯 测试几个点
    test_points = [
        (100, 100),
        (500, 300),
        (960, 540),   # 屏幕中心
        (1500, 800)
    ]

    for x, y in test_points:
        move_abs(ser, x, y, screen_w, screen_h)
        time.sleep(0.5)

    ser.close()