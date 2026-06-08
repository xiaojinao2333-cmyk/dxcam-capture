import serial
import serial.tools.list_ports
import time
import tkinter as tk

SERIAL_PORT = "COM11"
BAUDRATE = 115200

def build_packet(data_bytes):
    packet = [0x57, 0xAB, 0x00, 0x04, 0x07] + data_bytes
    checksum = sum(packet) & 0xFF
    packet.append(checksum)
    return bytes(packet)

def convert_to_4096(x, y, screen_w, screen_h):
    x_4096 = int(x * 4096 / screen_w)
    y_4096 = int(y * 4096 / screen_h)
    x_4096 = max(0, min(4095, x_4096))
    y_4096 = max(0, min(4095, y_4096))
    return x_4096, y_4096

def move_abs(ser, x, y, screen_w, screen_h):
    x_4096, y_4096 = convert_to_4096(x, y, screen_w, screen_h)
    x_low = x_4096 & 0xFF
    x_high = (x_4096 >> 8) & 0xFF
    y_low = y_4096 & 0xFF
    y_high = (y_4096 >> 8) & 0xFF
    data = [0x02, 0x00, x_low, x_high, y_low, y_high, 0x00]
    packet = build_packet(data)
    ser.write(packet)
    resp = ser.read(7)
    return packet, resp

class SerialSelector:
    def __init__(self, root):
        self.root = root
        self.root.title("串口选择器")
        self.root.geometry("400x300")

        self.selected_port = None
        self.running = True

        self.create_widgets()
        self.refresh_ports()

    def create_widgets(self):
        tk.Label(self.root, text="选择串口:", font=("Arial", 12)).pack(pady=10)

        self.port_listbox = tk.Listbox(self.root, font=("Arial", 10), height=8)
        self.port_listbox.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="刷新", command=self.refresh_ports, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="确定", command=self.on_select, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=self.on_cancel, width=10).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(self.root, text="正在扫描串口...", fg="blue")
        self.status_label.pack(pady=5)

    def refresh_ports(self):
        selection = self.port_listbox.curselection()
        selected_text = self.port_listbox.get(selection[0]) if selection else None

        self.port_listbox.delete(0, tk.END)
        ports = serial.tools.list_ports.comports()

        if not ports:
            self.port_listbox.insert(tk.END, "未找到串口")
            self.status_label.config(text="未找到串口，1秒后自动刷新...", fg="red")
        else:
            for port in ports:
                self.port_listbox.insert(tk.END, f"{port.device} - {port.description}")
            self.status_label.config(text=f"找到 {len(ports)} 个串口，1秒后自动刷新...", fg="green")

            if selected_text:
                for i in range(self.port_listbox.size()):
                    if self.port_listbox.get(i) == selected_text:
                        self.port_listbox.selection_set(i)
                        break

        if self.running:
            self.root.after(1000, self.refresh_ports)

    def on_select(self):
        selection = self.port_listbox.curselection()
        if selection:
            port_info = self.port_listbox.get(selection[0])
            self.selected_port = port_info.split(" - ")[0]
            self.running = False
            self.root.destroy()

    def on_cancel(self):
        self.selected_port = None
        self.running = False
        self.root.destroy()

def select_serial_port():
    root = tk.Tk()
    selector = SerialSelector(root)
    root.mainloop()
    return selector.selected_port

class CH9329Mouse:
    def __init__(self, port=None, baudrate=115200):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.screen_w = 1920
        self.screen_h = 1080

    def connect(self, port=None):
        if port:
            self.port = port
        if not self.port:
            return False

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            time.sleep(0.1)
            return True
        except serial.SerialException:
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def move_to(self, x, y):
        if not self.ser or not self.ser.is_open:
            return False
        try:
            packet, resp = move_abs(self.ser, x, y, self.screen_w, self.screen_h)
            return True
        except Exception:
            return False

    def set_screen_size(self, w, h):
        self.screen_w = w
        self.screen_h = h

def create_mouse():
    mouse = CH9329Mouse()

    port = select_serial_port()
    if not port:
        print("未选择串口，鼠标控制功能将不可用")
        return mouse

    if mouse.connect(port):
        print(f"CH9329 鼠标已连接: {port}")
    else:
        print(f"无法连接串口 {port}")

    return mouse
