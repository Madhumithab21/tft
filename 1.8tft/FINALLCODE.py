from machine import Pin, SPI, UART
import time
from math import sqrt
import os
from st7735 import TFT
from sysfont import sysfont
from ir_rx import NEC_16
from sdcard import SDCard

# --- TFT and SPI Setup ---
spi = SPI(2, baudrate=20000000, polarity=0, phase=0, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = TFT(spi, 16, 17, 18)  # CS, DC, RST
sd_cs = Pin(25, Pin.OUT)
sd = SDCard(spi, sd_cs)
os.mount(sd, "/sd")
tft.initr()
tft.rgb(True)
tft.width = 128
tft.height = 160

# --- UART for DFPlayer ---
uart = UART(2, baudrate=9600, tx=Pin(26), rx=Pin(27))

current_volume = 100  # Default volume

def send_dfplayer_command(cmd, param1=0, param2=0):
    command = bytearray(10)
    command[0] = 0x7E
    command[1] = 0xFF
    command[2] = 0x06
    command[3] = cmd
    command[4] = 0x00
    command[5] = param1
    command[6] = param2
    checksum = 0 - sum(command[1:7])
    command[7] = (checksum >> 8) & 0xFF
    command[8] = checksum & 0xFF
    command[9] = 0xEF
    uart.write(command)

def init_dfplayer():
    time.sleep(2)
    send_dfplayer_command(0x06, 0x00, current_volume)

def play_track(track=1):
    send_dfplayer_command(0x03, 0x00, track)
    print(f"🎵 Playing Track {track}")

def pause_resume():
    send_dfplayer_command(0x0E)

def show_volume():
    tft.text((35, 75), f"Volume: {current_volume}", YELLOW, sysfont)
    time.sleep(1)

def volume_up():
    global current_volume
    if current_volume < 100:
        current_volume += 30
        send_dfplayer_command(0x06, 0x00, current_volume)
        print(f"🔊 Volume: {current_volume}")
        show_volume()

def volume_down():
    global current_volume
    if current_volume > 0:
        current_volume -= 30
        send_dfplayer_command(0x06, 0x00, current_volume)
        print(f"🔉 Volume: {current_volume}")
        show_volume()

def color565(r, g, b): return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
def clamp(val, minval, maxval): return max(minval, min(maxval, val))

def display_bin_image(filename, width=128, height=160):
    try:
        with open(filename, "rb") as f:
            for y in range(height):
                line = f.read(width * 2)
                if not line or len(line) < width * 2:
                    break
                tft._setwindowloc((0, y), (width - 1, y))
                tft._writedata(line)
        print(f"✅ Displayed: {filename}")
    except Exception as e:
        print(f"❌ Error displaying {filename}: {e}")

YELLOW = color565(255, 204, 0)
WHITE = TFT.WHITE
BLACK = TFT.BLACK
BLUE = color565(0, 122, 255)

folders = [
    {"label": "3D", "x": 5, "y": 10},
    {"label": "Desk", "x": 48, "y": 10},
    {"label": "Docs", "x": 91, "y": 10},
    {"label": "Pics", "x": 5, "y": 60},
    {"label": "Music", "x": 48, "y": 60},
    {"label": "Murugan", "x": 91, "y": 60},
    {"label": "Videos", "x": 5, "y": 110},
]

selected_index = 0
previous_index = 0
music_mode = False
murugan_mode = False
current_track = 1
images = [f"/sd/image{i}.bin" for i in range(1, 4)]
murugan_images = [f"/sd/image/murugan ({i}).bin" for i in range(1, 21)]
image_index = 0
is_playing = True
power_state = False

def draw_folder(x, y, label, highlight=False):
    color = BLUE if highlight else YELLOW
    tft.fillrect((x, y + 5), (30, 25), color)
    tft.fillrect((x + 2, y), (28, 15), color)
    tft.fillrect((x + 2, y + 35), (28, 10), BLACK)
    tft.text((x + 2, y + 35), label, WHITE, sysfont)

def draw_folders_full():
    for i, folder in enumerate(folders):
        draw_folder(folder["x"], folder["y"], folder["label"], highlight=(i == selected_index))

def draw_folders_changed():
    global previous_index
    if previous_index != selected_index:
        draw_folder(folders[previous_index]["x"], folders[previous_index]["y"], folders[previous_index]["label"], False)
    draw_folder(folders[selected_index]["x"], folders[selected_index]["y"], folders[selected_index]["label"], True)
    previous_index = selected_index

def launch_music_mode():
    global music_mode, is_playing, image_index
    music_mode = True
    is_playing = True
    image_index = 0
    tft.fill(BLACK)
    init_dfplayer()
    play_track(current_track)

def launch_murugan_mode():
    global murugan_mode, is_playing, image_index
    murugan_mode = True
    is_playing = True
    image_index = 0
    tft.fill(BLACK)
    init_dfplayer()
    play_track(2)

def ir_callback(data, ctrl):
    global selected_index, previous_index
    global music_mode, murugan_mode, current_track, image_index, is_playing, power_state

    if data < 0:
        return

    print("IR Code: {:02x}".format(data))

    if data == 0x12:
        power_state = not power_state
        if power_state:
            music_mode = False
            murugan_mode = False
            tft.fill(BLACK)
            display_bin_image("/sd/logo.bin")
            time.sleep(2)
            tft.fill(BLACK)
            draw_folders_full()
        else:
            music_mode = False
            murugan_mode = False
            tft.fill(BLACK)
            display_bin_image("/sd/logo.bin")
            time.sleep(1)
            tft.fill(BLACK)

    elif data == 0x03:
        music_mode = False
        murugan_mode = False
        is_playing = False
        tft.fill(BLACK)
        draw_folders_full()

    elif data == 0x1E and not music_mode and not murugan_mode and power_state:
        selected_folder = folders[selected_index]["label"]
        print(f"📂 Selected: {selected_folder}")
        if selected_folder == "Music":
            launch_music_mode()
        elif selected_folder == "Murugan":
            launch_murugan_mode()

    elif data == 0x02:
        volume_up()
    elif data == 0x08:
        volume_down()
    elif data == 0x05:
        pause_resume()
        is_playing = not is_playing
        print("⏸️ Paused" if not is_playing else "▶️ Resumed")
    elif data == 0x09:
        current_track = (current_track % 10) + 1
        play_track(current_track)
    elif data == 0x04:
        previous_index = selected_index
        selected_index = (selected_index - 1) % len(folders)
        draw_folders_changed()
    elif data == 0x06:
        previous_index = selected_index
        selected_index = (selected_index + 1) % len(folders)
        draw_folders_changed()

# --- IR Setup ---
ir = NEC_16(Pin(32, Pin.IN), ir_callback)

# --- Main Loop ---
tft.fill(BLACK)

while True:
    if music_mode and is_playing:
        display_bin_image(images[image_index])
        image_index = (image_index + 1) % len(images)
        time.sleep(2)
    elif murugan_mode and is_playing:
        display_bin_image(murugan_images[image_index])
        image_index = (image_index + 1) % len(murugan_images)
        time.sleep(2)
    else:
        time.sleep(0.1)
