import socket
import json
import threading
import base64
import os
import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# Directory paths for saving images
BASE_DIR = 'images'
WEB_CAM_DIR = os.path.join(BASE_DIR, 'webcam')
RECEIVED_DIR = os.path.join(BASE_DIR, 'received')

# Create directories if they don't exist
os.makedirs(WEB_CAM_DIR, exist_ok=True)
os.makedirs(RECEIVED_DIR, exist_ok=True)

client_socket = None
max_file_size = None


def open_images_folder():
  folder_path = os.path.abspath(WEB_CAM_DIR )
  os.startfile(folder_path)


def connect_to_server():
  global client_socket
  client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

  def connect_and_listen():
    try:
      client_socket.connect(('localhost', 12345))
      update_status("Đã kết nối tới server")
      listen_for_server_messages()  # Listen for messages from the server
    except Exception as e:
      messagebox.showerror("Lỗi", f"Không thể kết nối đến server: {e}")

  # Create a new thread to handle connection and listen for server messages
  connect_thread = threading.Thread(target=connect_and_listen)
  connect_thread.start()


def disconnect_from_server():
  global client_socket
  if client_socket:
    client_socket.close()
    client_socket = None
    update_status("Chưa kết nối đến server")
  else:
    messagebox.showwarning("Cảnh báo", "Chưa kết nối đến server")
def update_status(message):
  status_label.config(text=message)


def listen_for_server_messages():
  global max_file_size
  while True:
    try:
      message = b''
      while True:
        part = client_socket.recv(1024)
        if not part:
          update_status("Chưa kết nối đến server")
          return  # Connection closed by server
        message += part
        if b'\n' in part:
          break
      message = message.decode().strip()
      if message:
        message_json = json.loads(message)
        if message_json.get('type') == 'file_size_limit':
          max_file_size = message_json.get('max_size', None)
          if max_file_size is not None:
            max_file_size = int(max_file_size)
            update_status(f"Giới hạn dung lượng ảnh gửi đi: {max_file_size / (1024 * 1024):.2f}MB")
          else:
            update_status("Chưa giới hạn ảnh từ bên server")
        elif message_json.get('type') == 'server_disconnected':
          update_status("Chưa kết nối đến server")

    except Exception as e:
      break


def reduce_image_size(image_path, max_size, initial_quality=85, quality_step=10):
  """Reduce image size by decreasing quality and resizing if necessary."""
  image = Image.open(image_path)
  temp_image_path = os.path.join(WEB_CAM_DIR, 'temp.jpg')

  while True:
    image.save(temp_image_path, quality=initial_quality)

    file_size = os.path.getsize(temp_image_path)
    if file_size <= max_size:
      break

    # Resize the image if it's still too large
    width, height = image.size
    new_width = int(width * 0.8)
    new_height = int(height * 0.8)
    image = image.resize((new_width, new_height), Image.LANCZOS)

    # Reduce the quality more
    initial_quality -= quality_step
    if initial_quality <= 10:
      break  # Don't reduce quality below a minimum threshold

  return temp_image_path


def send_image(image_path):
  global max_file_size
  temp_image_path = None
  is_reduced = False

  try:
    file_size = os.path.getsize(image_path)

    # Check if a file size limit has been set by the server
    if max_file_size is not None and isinstance(max_file_size, int):
      if file_size > max_file_size:
        user_choice = messagebox.askyesno("Cảnh báo",
                                          "Ảnh đã vượt quá giới hạn và sẽ bị giảm chất lượng ảnh. Bạn có muốn tiếp tục không?")

        if user_choice:
            # Nếu người dùng chọn "Có", giảm chất lượng và gửi ảnh
           temp_image_path = reduce_image_size(image_path, max_file_size)
           image_path = temp_image_path
           file_size = os.path.getsize(image_path)
           is_reduced = True

           if file_size > max_file_size:
              messagebox.showerror("Lỗi", "Ảnh vẫn quá lớn và sẽ không thể gửi đi")
              return

        else:
          # Nếu người dùng chọn "Không", hiển thị thông báo lỗi và dừng lại
          messagebox.showerror("Lỗi", "Không gửi được ảnh đến server")
          return

    with open(image_path, 'rb') as f:
      image_data = f.read()

    image_name = os.path.basename(image_path)
    if is_reduced:
      image_name = f'Reduce_image{len(os.listdir(RECEIVED_DIR)) + 1}.jpg'


    encoded_image_data = base64.b64encode(image_data).decode('utf-8')

    data = {'type': 'upload', 'name': image_name, 'data': encoded_image_data}
    data_json = json.dumps(data) + '\n'

    client_socket.send(data_json.encode())
    messagebox.showinfo("Thông báo", f"Ảnh {image_name} đã được gửi tới Server")
  except Exception as e:
    messagebox.showerror("Error", f"Lỗi gửi ảnh: {e}")
  finally:
    if temp_image_path and os.path.exists(temp_image_path):
      os.remove(temp_image_path)


def update_frame():
  ret, frame = cap.read()
  if ret:
    cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(cv2_image)
    photo = ImageTk.PhotoImage(image=image)
    camera_label.config(image=photo)
    camera_label.image = photo
  camera_window.after(10, update_frame)


def capture_image():
  global cap
  cap = cv2.VideoCapture(0)
  if not cap.isOpened():
    messagebox.showerror("Lỗi", "Không thể mở webcam")
    return

  global camera_window, camera_label
  camera_window = tk.Toplevel()
  camera_window.title("Camera")

  camera_label = tk.Label(camera_window)
  camera_label.pack()

  capture_button = tk.Button(camera_window, text="Chụp ảnh", command=lambda: capture_and_send(cap, camera_window))
  capture_button.pack(pady=20)

  update_frame()


def capture_and_send(cap, camera_window):
  ret, frame = cap.read()
  if not ret:
    messagebox.showerror("Lỗi", "Không thể chụp ảnh")
    return

  image_index = len(os.listdir(WEB_CAM_DIR)) + 1
  image_name = f'webcam{image_index}.jpg'
  image_path = os.path.join(WEB_CAM_DIR, image_name)
  cv2.imwrite(image_path, frame)

  send_image(image_path)

  cap.release()
  camera_window.destroy()


def choose_image_file():
  image_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.jpeg;*.png")])
  if image_path:
    send_image(image_path)


def create_client_gui():
  global status_label  # Ensure status_label is globally accessible
  root = tk.Tk()
  root.title("Client")
  root.geometry('450x400')
  root.resizable(width=False, height=False)
  root.attributes("-topmost", True)
  root.configure(bg="white")

  connect_button = tk.Button(root, text="Kết nối tới server", command=connect_to_server)
  connect_button.pack(pady=10)

  status_label = tk.Label(root, text="Chưa kết nối đến server")
  status_label.pack(pady=10)

  disconnect_button = tk.Button(root, text="Ngắt kết nối", command=disconnect_from_server)
  disconnect_button.pack(pady=10)

  # Đọc đường dẫn ảnh từ tệp JSON
  with open('config.json', 'r') as file:
    data = json.load(file)
    img_path = data['client_path']

  img = Image.open("D:\\Ungdungquanlyhinhanh_nhom10\\hinhanh.jpg")
  img = img.resize((250, 150), Image.LANCZOS)  # Resize the image if necessary
  img = ImageTk.PhotoImage(img)
  img_label = tk.Label(root, image=img, bg="white")
  img_label.pack(pady=10)

  button_frame = tk.Frame(root, bg="white")
  button_frame.pack(side=tk.BOTTOM, pady=20)

  choose_image_button = tk.Button(button_frame, text="Chọn ảnh từ thiết bị", command=choose_image_file)
  choose_image_button.pack(side=tk.LEFT, padx=20)

  open_folder_button = tk.Button(button_frame, text="Xem ảnh", command=open_images_folder)
  open_folder_button.pack(side=tk.LEFT, padx=20)

  capture_image_button = tk.Button(button_frame, text="Chụp ảnh từ camera", command=capture_image)
  capture_image_button.pack(side=tk.LEFT, padx=20)



  root.mainloop()


if __name__ == "__main__":
  create_client_gui()
