DIY Video Doorbell, built right from scratch!
Powered by a Raspberry Pi and a wide angle rpi camera module 3, this system features a full 7-inch touch display. On boot, it loads a sleek dashboard with a vector clock, real-time date, and network details.
It includes a magnetic door sensor that automatically cuts off the live video stream the moment the door opens for safety. With dedicated controls, you can launch a live HD video feed, capture high-res photos, and browse saved images through a built-in gallery—all controlled by customized Python and Tkinter software.
A complete smart home project combining hardware, hardware safety interrupts, and custom software UI!

**Installation steps**
Step_1: copy the deoorbell.py file into /home/pi directory
Step_2: change the permission 
`chmod +x /home/pi/doorbell.py`
Step_3: Create the autostart directory if it doesn't already exist:
`mkdir -p ~/.config/autostart`
Step_4: Create a new autostart configuration entry
`nano ~/.config/autostart/doorbell.desktop`
Step_5: copy the content of doorbell.desktop from paste into **.config/autostart/doorbell.deskto**
Step_6: install all the packages using below single command
`sudo apt update && sudo apt install -y \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    python3-gpiozero \
    rpicam-apps`

Schematic
<img width="3000" height="2476" alt="circuit_image (2)" src="https://github.com/user-attachments/assets/142d9b61-7ce5-4a2f-b89c-ca4cc451cc52" />
