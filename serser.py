import os
import json
import socket
import base64
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from PIL import Image, ImageTk
from datetime import datetime

HOST = 'localhost'
PORT = 12345

BASE_DIR = 'images'
RECEIVED_DIR = os.path.join(BASE_DIR, 'received')
WEB_CAM_DIR = os.path.join(BASE_DIR, 'webcam')

os.makedirs(RECEIVED_DIR, exist_ok=True)
os.makedirs(WEB_CAM_DIR, exist_ok=True)

server_socket = None
server_running = False
client_socket = None
file_size_limit = None
stop_thread = False
treeview = None
def handle_client(client_socket):
    global file_size_limit, treeview
    reduce_image_counter = 1
    while True:
        try:
            data = b''
            while True:
                part = client_socket.recv(1024)
                if not part:
                    return  # Ngắt kết nối từ client
                data += part
                if b'\n' in part:
                    break

            if data:
                data = data.decode().strip()
                data_json = json.loads(data)
                request_type = data_json.get('type')

                if request_type == 'upload':
                    image_name = data_json['name']
                    encoded_image_data = data_json['data']
                    image_data = base64.b64decode(encoded_image_data)
                    # Nếu tên ảnh chứa 'Reduce_image', lưu ảnh giảm chất lượng
                    if 'Reduce_image' in image_name:
                        receive_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        reduce_image_path = os.path.join(RECEIVED_DIR, image_name)

                        with open(reduce_image_path, 'wb') as f:
                            f.write(image_data)
                        file_size = os.path.getsize(reduce_image_path)
                        treeview.insert('', tk.END, values=(image_name, f"{file_size // 1024} KB", receive_time))
                        treeview.yview(tk.END)
                        print(f"Received and saved reduced image {image_name}")
                    else:
                        # Lưu ảnh gốc
                        receive_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        original_image_path = os.path.join(RECEIVED_DIR, image_name)
                        with open(original_image_path, 'wb') as f:
                            f.write(image_data)
                        file_size = os.path.getsize(original_image_path)
                        treeview.insert('', tk.END, values=(image_name, f"{file_size // 1024} KB", receive_time))
                        treeview.yview(tk.END)
                        print(f"Received and saved original image {image_name}")

        except Exception as e:
            print(f"Error handling client: {e}")
            break
    # Cập nhật trạng thái sau khi client ngắt kết nối
    update_status("Server khởi động và lắng nghe trên port 12345...")

def start_server():
    global server_socket, server_running, client_socket,stop_thread
    if server_running:
        messagebox.showwarning("Cảnh báo", "Server đã chạy.")
        return

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    server_running = True
    stop_thread = False  # Cho phép thread chạy
    update_status("Server khởi động và lắng nghe trên port 12345...")

    ip_address = socket.gethostbyname(socket.gethostname())
    ip_port_label.config(text=f"Server IP: {ip_address}, Port: {PORT}")

    def accept_and_handle_client():
        global client_socket, stop_thread
        while not stop_thread:  # Kiểm tra xem có cần dừng thread không
            try:
                client_socket, addr = server_socket.accept()
                if stop_thread:
                    break
                update_status(f"Chấp nhận kết nối từ {addr}")
                send_file_size_limit_to_client()  # Gửi giới hạn dung lượng ngay sau khi client kết nối
                handle_client(client_socket)  # Xử lý client
            except Exception as e:
                if server_running:
                    print(f"Error accepting client: {e}")
                break

    client_thread = threading.Thread(target=accept_and_handle_client)
    client_thread.start()

# Hàm ngắt kết nối server
def disconnect_server():
    global server_socket, server_running, client_socket
    if server_running:
        # Đóng kết nối với client nếu còn kết nối
        if client_socket:
            client_socket.close()
            client_socket = None

        server_socket.close()
        server_socket = None
        server_running = False

        update_status("Server đã đóng kết nối")
        ip_port_label.config(text="Server IP: Chưa khởi động")

        # Thông báo cho client rằng server đã ngắt kết nối
        try:
            data = {'type': 'server_disconnected'}
            client_socket.send(json.dumps(data).encode() + b'\n')
        except Exception as e:
            print(f"Error sending disconnection message to client: {e}")
    else:
        update_status("Server chưa được khởi động")


def update_status(message):
    status_label.config(text=message)


# Đọc cấu hình từ tệp JSON
def load_config():
    with open('config.json', 'r') as file:
        config = json.load(file)
        return config['received_dir']


def open_storage_folders():
    global treeview
    RECEIVED_DIR = load_config()  # Đọc đường dẫn thư mục từ tệp JSON

    VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}

    def update_treeview():
        for item in treeview.get_children():
            treeview.delete(item)

        for filename in os.listdir(RECEIVED_DIR):
            if filename.lower().endswith(tuple(VALID_EXTENSIONS)):
                file_path = os.path.join(RECEIVED_DIR, filename)
                size = os.path.getsize(file_path)
                receive_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                treeview.insert('', tk.END, values=(filename, f"{size // 1024} KB", receive_time))

    def search_images():
        query = search_entry.get().lower()
        for item in treeview.get_children():
            treeview.delete(item)

        for file in os.listdir(RECEIVED_DIR):
            if file.lower().endswith(tuple(VALID_EXTENSIONS)) and query in file.lower():
                file_path = os.path.join(RECEIVED_DIR, file)
                size = os.path.getsize(file_path)
                receive_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                treeview.insert('', tk.END, values=(file, f"{size // 1024} KB", receive_time))

    def rename_image():
        selected_item = treeview.selection()
        if not selected_item:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ảnh để đổi tên.")
            return

        old_name = treeview.item(selected_item)['values'][0]
        new_name = simpledialog.askstring("Đổi tên", "Nhập tên mới cho ảnh:", initialvalue=old_name)

        if new_name:
            # Kiểm tra đuôi của tên file mới
            if not any(new_name.lower().endswith(ext) for ext in VALID_EXTENSIONS):
                messagebox.showerror("Lỗi", "Tên file phải có đuôi là .png, .jpg, .jpeg, hoặc .gif.")
                return

            old_path = os.path.join(RECEIVED_DIR, old_name)
            new_path = os.path.join(RECEIVED_DIR, new_name)
            if os.path.exists(new_path):
                messagebox.showerror("Lỗi", "Tên mới đã tồn tại.")
                return
            try:
                os.rename(old_path, new_path)
                update_treeview()  # Cập nhật danh sách ảnh trong Treeview
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đổi tên ảnh: {e}")

    def delete_image():
        selected_item = treeview.selection()
        if not selected_item:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ảnh để xóa.")
            return

        filename = treeview.item(selected_item)['values'][0]
        file_path = os.path.join(RECEIVED_DIR, filename)
        if messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa ảnh {filename}?"):
            try:
                os.remove(file_path)
                update_treeview()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa ảnh: {e}")

    def show_image_preview(event):
        selected_item = treeview.selection()
        if selected_item:
            filename = treeview.item(selected_item)['values'][0]
            image_path = os.path.join(RECEIVED_DIR, filename)
            try:
                image = Image.open(image_path)
                image = ImageTk.PhotoImage(image)
                preview_window = tk.Toplevel()
                preview_window.title("Ảnh xem trước")
                tk.Label(preview_window, image=image).pack()
                preview_window.image = image  # Giữ tham chiếu đến hình ảnh
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở ảnh: {e}")

    # Tạo cửa sổ mới
    image_window = tk.Toplevel()
    image_window.title("Danh sách ảnh")
    image_window.geometry('700x400')

    # Tạo Treeview và scrollbar
    columns = ("filename", "size", "receive_time")
    treeview = ttk.Treeview(image_window, columns=columns, show='headings')
    treeview.heading("filename", text="Tên ảnh")
    treeview.heading("size", text="Dung lượng")
    treeview.heading("receive_time", text="Thời gian")
    treeview.pack(pady=10, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(image_window, orient=tk.VERTICAL, command=treeview.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    treeview.config(yscrollcommand=scrollbar.set)

    # Thêm thanh tìm kiếm
    search_frame = tk.Frame(image_window)
    search_frame.pack(pady=5)

    search_entry = tk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    search_button = tk.Button(search_frame, text="Tìm kiếm", command=search_images)
    search_button.pack(side=tk.LEFT)

    # Thêm các nút đổi tên và xóa
    button_frame = tk.Frame(image_window)
    button_frame.pack(pady=10)

    rename_button = tk.Button(button_frame, text="Đổi tên", command=rename_image)
    rename_button.pack(side=tk.LEFT, padx=5)

    delete_button = tk.Button(button_frame, text="Xóa", command=delete_image)
    delete_button.pack(side=tk.LEFT, padx=5)

    update_treeview()

    # Liên kết sự kiện chọn item với hàm show_image_preview
    treeview.bind("<Double-1>", show_image_preview)


def send_file_size_limit_to_client():
    global client_socket, file_size_limit
    if client_socket:
        try:
            data = {'type': 'file_size_limit', 'max_size': file_size_limit}
            client_socket.send(json.dumps(data).encode() + b'\n')
        except Exception as e:
            print(f"Error sending file size limit to client: {e}")

def set_file_size_limit():
    global file_size_limit
    limit = simpledialog.askfloat("Nhập giới hạn", "Nhập giới hạn kích thước ảnh (MB):")
    if limit is not None:
        if limit <= 0:
            file_size_limit = None
            messagebox.showinfo("Thông báo", "Không có giới hạn kích thước ảnh")
        else:
            file_size_limit = limit * 1024 * 1024  # Chuyển đổi MB sang bytes
            messagebox.showinfo("Thông báo", f"Giới hạn kích thước ảnh đã được đặt: {limit}MB")
        send_file_size_limit_to_client()

def reset_settings():
    global file_size_limit
    file_size_limit = None
    messagebox.showinfo("Thông báo", "Các cài đặt đã được thiết lập lại")
    send_file_size_limit_to_client()  # Cập nhật thông tin cho client



def create_server_gui():
    global status_label, ip_port_label

    # Đọc đường dẫn ảnh từ tệp JSON
    with open('config.json', 'r') as file:
        data = json.load(file)
        img_path = data['server_path']

    root = tk.Tk()
    root.title("Server")
    root.geometry('400x400')
    root.resizable(width=False, height=False)
    root.attributes("-topmost",True)
    root.configure(bg="white")
    # Mở và hiển thị ảnh từ đường dẫn trong JSON
    img = Image.open("D:\\Ungdungquanlyhinhanh_nhom10\\hinhanh.jpg")
    img = img.resize((150, 150), Image.LANCZOS)  # Resize the image if necessary
    img = ImageTk.PhotoImage(img)
    img_label = tk.Label(root, image=img, bg="white")
    img_label.pack(pady=10)
    # Start Server button and status labels below the image
    start_button = tk.Button(root, text="Khởi động server", command=start_server)
    start_button.pack(pady=10)

    disconnect_button = tk.Button(root, text="Ngắt kết nối", command=disconnect_server)
    disconnect_button.pack(pady=10)

    status_label = tk.Label(root, text="Server chưa khởi động.", bg="white")
    status_label.pack(pady=5)

    ip_port_label = tk.Label(root, text="Server IP: Chưa khởi động", bg="white")
    ip_port_label.pack(pady=5)

    # Place the three remaining buttons at the bottom, evenly spaced
    button_frame = tk.Frame(root, bg="white")
    button_frame.pack(side=tk.BOTTOM, pady=20)

    open_folder_button = tk.Button(button_frame, text="Xem ảnh", command=open_storage_folders)
    open_folder_button.pack(side=tk.LEFT, padx=20)

    set_limit_button = tk.Button(button_frame, text="Đặt giới hạn kích thước tệp", command=set_file_size_limit)
    set_limit_button.pack(side=tk.LEFT, padx=20)

    reset_limit_button = tk.Button(button_frame, text="Thiết lập lại", command=reset_settings)
    reset_limit_button.pack(side=tk.LEFT, padx=20)

    root.mainloop()

if __name__ == "__main__":
    create_server_gui()
