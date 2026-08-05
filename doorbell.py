import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from gpiozero import Button
import math
import time
import subprocess
import os
import signal
import socket
import glob

# --- CONFIGURATION ---
BUTTON_PIN = 22       # GPIO pin for physical doorbell button
MAGNET_PIN = 27       # GPIO pin for door magnet sensor (Grounded when door is CLOSED)
FRAME_WIDTH = 800     # Full width of 7-inch display
FRAME_HEIGHT = 480    # Full height of 7-inch display
IMAGE_DIR = "/home/pi/doorbell_images"  # Directory for storing saved photos

# Ensure image storage directory exists
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- CAMERA CONFIGURATION ---
USING_MODULE_3 = True  # Enabled for Raspberry Pi Camera Module 3 Wide

def get_ip_address():
    """Dynamically fetches the Raspberry Pi's current network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Not Connected"

class VideoDoorbellApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Pi Doorbell System")
        self.window.attributes('-fullscreen', True)
        self.window.configure(bg='black')

        # State variables
        self.is_streaming = False
        self.is_viewing_photos = False
        self.video_process = None
        self.image_files = []
        self.current_image_index = 0
        self.tk_photo = None  # Prevent garbage collection of image

        # Setup GUI Components
        self.create_widgets()

        # Setup Hardware (Using internal pull-up resistors)
        # Pin 27 grounded = door_sensor.is_pressed == True
        self.doorbell = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
        self.door_sensor = Button(MAGNET_PIN, pull_up=True, bounce_time=0.05)

        # Hardware Event Interrupts
        self.doorbell.when_pressed = self.on_doorbell_pressed

        # MAGNET SENSOR LOGIC:
        # Door Open (Pin 27 Ungrounded) -> Immediately stop video feed
        self.door_sensor.when_released = self.on_door_opened

        # Start background clock update cycle (App defaults to Dashboard Home on reboot)
        self.update_clock()

    def create_widgets(self):
        # 1. Main Upper Frame for Video/Dashboard/Photo Layout
        self.display_frame = tk.Frame(self.window, bg='black', width=FRAME_WIDTH, height=400)
        self.display_frame.pack_propagate(False)
        self.display_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Video Canvas placeholder for rpicam overlay
        self.video_canvas = tk.Canvas(self.display_frame, bg='black', highlightthickness=0)

        # Photo Viewer Frame
        self.photo_frame = tk.Frame(self.display_frame, bg='black')
        self.photo_label = tk.Label(self.photo_frame, bg='black')
        self.photo_label.pack(expand=True, fill=tk.BOTH)

        # Photo Gallery Navigation Controls Overlay
        self.photo_nav_frame = tk.Frame(self.photo_frame, bg='black')
        self.photo_nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=4)

        self.prev_btn = tk.Button(
            self.photo_nav_frame, text="< Previous", font=("Arial", 14, "bold"),
            bg="#333333", fg="white", activebackground="#555555", activeforeground="white",
            command=self.show_prev_photo
        )
        self.prev_btn.pack(side=tk.LEFT, padx=20)

        self.photo_counter_label = tk.Label(
            self.photo_nav_frame, text="", font=("Arial", 14, "bold"), fg="white", bg="black"
        )
        self.photo_counter_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(
            self.photo_nav_frame, text="Next >", font=("Arial", 14, "bold"),
            bg="#333333", fg="white", activebackground="#555555", activeforeground="white",
            command=self.show_next_photo
        )
        self.next_btn.pack(side=tk.RIGHT, padx=20)

        # Capture Status Overlay Label (displays photo saved notifications)
        self.status_label = tk.Label(
            self.display_frame,
            text="",
            font=("Arial", 16, "bold"),
            fg="#00FF00",
            bg="black"
        )

        # --- IDLE DASHBOARD PANELS ---
        self.dashboard_frame = tk.Frame(self.display_frame, bg='black')
        self.dashboard_frame.pack(fill=tk.BOTH, expand=True)

        # Left Side Container (Clock + Digital Readouts)
        self.left_panel = tk.Frame(self.dashboard_frame, bg='black', width=380)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.left_center_container = tk.Frame(self.left_panel, bg='black')
        self.left_center_container.pack(expand=True)

        # Vector Analog Clock Canvas
        self.clock_canvas = tk.Canvas(self.left_center_container, width=360, height=360, bg='black', highlightthickness=0)
        self.clock_canvas.pack(anchor=tk.CENTER)

        # Digital Time Label
        self.digital_time_label = tk.Label(self.left_center_container, text="", font=("Arial", 28, "bold"), fg="white", bg="black")
        self.digital_time_label.pack(pady=(2, 0), anchor=tk.CENTER)

        # Date Display Readout
        self.digital_date_label = tk.Label(self.left_center_container, text="", font=("Arial", 18, "bold"), fg="#00FF00", bg="black")
        self.digital_date_label.pack(anchor=tk.CENTER)

        # Right Side Container (Metadata)
        self.right_panel = tk.Frame(self.dashboard_frame, bg='black', width=420)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=20)

        self.text_center_container = tk.Frame(self.right_panel, bg='black')
        self.text_center_container.pack(expand=True)

        # Project Metadata Labels
        tk.Label(self.text_center_container, text="Project: DIY Video Doorbell", font=("Arial", 22, "bold"), fg="white", bg="black", anchor="w").pack(fill=tk.X, pady=6)
        tk.Label(self.text_center_container, text="Engineered By: [ADD_YOUR_NAME]", font=("Arial", 22, "bold"), fg="white", bg="black", anchor="w").pack(fill=tk.X, pady=6)

        ip_string = f"IP Address: {get_ip_address()}"
        tk.Label(self.text_center_container, text=ip_string, font=("Arial", 22, "bold"), fg="white", bg="black", anchor="w").pack(fill=tk.X, pady=6)

        # 2. Bottom Control Panel
        self.btn_panel = tk.Frame(self.window, bg='black', height=80)
        self.btn_panel.pack_propagate(False)
        self.btn_panel.pack(side=tk.BOTTOM, fill=tk.X)

        # Button 1: Live View / Stop View
        self.live_view_btn = tk.Button(
            self.btn_panel,
            text="Live View",
            command=self.toggle_stream,
            font=("Arial", 16, "bold"),
            bg="#39FF14",                    # Neon Green
            fg="black",
            activebackground="#26cc0c",
            activeforeground="black",
            bd=1,
            relief=tk.RAISED
        )
        self.live_view_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Button 2: Capture Photo
        self.capture_btn = tk.Button(
            self.btn_panel,
            text="Capture Photo",
            command=self.capture_photo,
            font=("Arial", 16, "bold"),
            bg="#00BFFF",                    # Deep Sky Blue
            fg="black",
            activebackground="#009ACD",
            activeforeground="black",
            bd=1,
            relief=tk.RAISED
        )
        self.capture_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Button 3: Show Photo / Close Photo
        self.show_photo_btn = tk.Button(
            self.btn_panel,
            text="Show Photo",
            command=self.toggle_photo_viewer,
            font=("Arial", 16, "bold"),
            bg="#FFD700",                    # Vivid Gold
            fg="black",
            activebackground="#E6C200",
            activeforeground="black",
            bd=1,
            relief=tk.RAISED
        )
        self.show_photo_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Button 4: Reboot System
        self.reboot_btn = tk.Button(
            self.btn_panel,
            text="Reboot System",
            command=self.reboot_system,
            font=("Arial", 16, "bold"),
            bg="#FF3B30",                    # Warning Red
            fg="white",
            activebackground="#C3271D",
            activeforeground="white",
            bd=1,
            relief=tk.RAISED
        )
        self.reboot_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

    def on_door_opened(self):
        """Hardware callback: Triggers when Pin 27 ungrounded (door opened)."""
        self.window.after(0, self.stop_stream)

    def on_doorbell_pressed(self):
        """Hardware callback for physical doorbell button."""
        self.window.after(0, self.start_stream)

    def update_clock(self):
        """Draws vector analog clock."""
        t = time.localtime()
        time_str = time.strftime("%H:%M:%S") + "  IST"
        date_str = time.strftime("%A, %d %B %Y")

        self.digital_time_label.config(text=time_str)
        self.digital_date_label.config(text=date_str)

        if not self.is_streaming and not self.is_viewing_photos:
            self.clock_canvas.delete("all")
            cx, cy, r = 180, 180, 165

            self.clock_canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#F5F5F5", outline="#E0E0E0", width=2)
            self.clock_canvas.create_oval(cx-6, cy-6, cx+6, cy+6, fill="black")

            for i in range(1, 13):
                angle = (i * 30) * math.pi / 180
                num_x = cx + (r - 28) * math.sin(angle)
                num_y = cy - (r - 28) * math.cos(angle)
                self.clock_canvas.create_text(num_x, num_y, text=str(i), fill="#555555", font=("Arial", 16, "bold"))

            hr, mn, sc = t.tm_hour, t.tm_min, t.tm_sec

            angle_sec = math.pi/2 - (sc * (math.pi / 30))
            angle_min = math.pi/2 - (mn * (math.pi / 30))
            angle_hr  = math.pi/2 - ((hr % 12 + mn / 60.0) * (math.pi / 6))

            self.clock_canvas.create_line(cx, cy, cx + (r-24)*math.cos(angle_sec), cy - (r-24)*math.sin(angle_sec), fill="#FF3B30", width=2)
            self.clock_canvas.create_line(cx, cy, cx + (r-38)*math.cos(angle_min), cy - (r-38)*math.sin(angle_min), fill="#1C1C1E", width=4)
            self.clock_canvas.create_line(cx, cy, cx + (r-65)*math.cos(angle_hr), cy - (r-65)*math.sin(angle_hr), fill="#1C1C1E", width=6)

        self.window.after(1000, self.update_clock)

    def toggle_stream(self):
        if self.is_streaming:
            self.stop_stream()
        else:
            self.start_stream()

    def start_stream(self):
        # BLOCK opening feed if door is OPEN (Pin 27 not grounded)
        if not self.door_sensor.is_pressed:
            self.show_status("Door Open: Video Feed Blocked")
            return

        if not self.is_streaming:
            # Close photo viewer if open
            if self.is_viewing_photos:
                self.close_photo_viewer()

            self.is_streaming = True
            self.live_view_btn.config(text="Stop View", bg="#FF3B30", fg="white")

            self.dashboard_frame.pack_forget()
            self.video_canvas.pack(expand=True, fill=tk.BOTH)

            # Refresh GUI geometry
            self.window.update_idletasks()
            self.window.update()

            x = max(0, self.video_canvas.winfo_rootx())
            y = max(0, self.video_canvas.winfo_rooty())
            w = self.video_canvas.winfo_width() or FRAME_WIDTH
            h = self.video_canvas.winfo_height() or 400

            cmd = [
                "rpicam-vid",
                "-t", "0",
                "--width", "1920",
                "--height", "1080",
                "--inline",
                "--preview", f"{x},{y},{w},{h}",
                "--fullscreen", "0",
                "--metering", "average",
                "--ev", "1.8",
                "--framerate", "25",
                "--denoise", "cdn_fast"
            ]

            if USING_MODULE_3:
                cmd.extend(["--autofocus-mode", "continuous"])

            self.video_process = subprocess.Popen(cmd, preexec_fn=os.setsid)

    def stop_stream(self):
        """Terminates rpicam video feed process."""
        if self.is_streaming:
            self.is_streaming = False
            self.live_view_btn.config(text="Live View", bg="#39FF14", fg="black")

            if self.video_process:
                try:
                    os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                    self.video_process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(self.video_process.pid), signal.SIGKILL)
                        self.video_process.wait()
                    except Exception:
                        pass
                except Exception:
                    pass
                self.video_process = None

            self.video_canvas.pack_forget()
            if not self.is_viewing_photos:
                self.dashboard_frame.pack(fill=tk.BOTH, expand=True)

    def capture_photo(self):
        """Captures a still image."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(IMAGE_DIR, f"doorbell_{timestamp}.jpg")

        was_streaming = self.is_streaming
        if was_streaming:
            self.stop_stream()

        cmd = [
            "rpicam-still",
            "-o", filename,
            "--width", "1920",
            "--height", "1080",
            "--metering", "average",
            "--ev", "1.8",
            "-t", "1000"
        ]

        if USING_MODULE_3:
            cmd.extend(["--autofocus-mode", "auto"])

        try:
            subprocess.run(cmd, check=True)
            self.show_status(f"Saved: doorbell_{timestamp}.jpg")
        except Exception:
            self.show_status("Capture Failed!")

        if was_streaming and self.door_sensor.is_pressed:
            self.start_stream()

    # --- PHOTO VIEWER METHODS ---
    def toggle_photo_viewer(self):
        if self.is_viewing_photos:
            self.close_photo_viewer()
        else:
            self.open_photo_viewer()

    def open_photo_viewer(self):
        if self.is_streaming:
            self.stop_stream()

        self.image_files = sorted(
            glob.glob(os.path.join(IMAGE_DIR, "*.jpg")),
            key=os.path.getmtime,
            reverse=True
        )

        if not self.image_files:
            self.show_status("No saved photos found!")
            return

        self.is_viewing_photos = True
        self.current_image_index = 0

        self.dashboard_frame.pack_forget()
        self.photo_frame.pack(fill=tk.BOTH, expand=True)
        self.show_photo_btn.config(text="Close Photo", bg="#FF3B30", fg="white")

        self.render_current_photo()

    def close_photo_viewer(self):
        self.is_viewing_photos = False
        self.photo_frame.pack_forget()
        self.dashboard_frame.pack(fill=tk.BOTH, expand=True)
        self.show_photo_btn.config(text="Show Photo", bg="#FFD700", fg="black")

    def render_current_photo(self):
        if not self.image_files:
            return

        image_path = self.image_files[self.current_image_index]
        try:
            pil_img = Image.open(image_path)
            pil_img.thumbnail((780, 350), Image.Resampling.LANCZOS)
            self.tk_photo = ImageTk.PhotoImage(pil_img)
            self.photo_label.config(image=self.tk_photo)

            total = len(self.image_files)
            filename = os.path.basename(image_path)
            self.photo_counter_label.config(
                text=f"{self.current_image_index + 1} of {total}  ({filename})"
            )
        except Exception:
            self.photo_counter_label.config(text="Error loading image")

    def show_prev_photo(self):
        if self.image_files:
            self.current_image_index = (self.current_image_index - 1) % len(self.image_files)
            self.render_current_photo()

    def show_next_photo(self):
        if self.image_files:
            self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
            self.render_current_photo()

    def show_status(self, message):
        self.status_label.config(text=message)
        self.status_label.pack(side=tk.BOTTOM, pady=5)
        self.window.after(3000, lambda: self.status_label.pack_forget())

    def reboot_system(self):
        confirm = messagebox.askyesno("Reboot System", "Are you sure you want to reboot the Raspberry Pi?")
        if confirm:
            self.stop_stream()
            os.system("sudo reboot")

    def on_close(self):
        self.stop_stream()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoDoorbellApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
