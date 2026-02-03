from machine import Pin, SPI, UART
import time
from math import sqrt

from st7735 import TFT
from sysfont import sysfont
from ir_rx import NEC_16

# --- TFT and SPI Setup ---
spi = SPI(2, baudrate=20000000, polarity=0, phase=0,
          sck=Pin(14), mosi=Pin(13), miso=Pin(12))
tft = TFT(spi, 16, 17, 18)  # CS, DC, RST
tft.initr()
tft.rgb(True)

# Manually define width and height (common for 1.8" ST7735)
tft.width = 128
tft.height = 160

# --- UART for DFPlayer ---
uart = UART(2, baudrate=9600, tx=Pin(26), rx=Pin(27))

# --- DFPlayer Command Sender ---
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

# --- DFPlayer Functions ---
def init_dfplayer():
    time.sleep(2)
    send_dfplayer_command(0x06, 0x00, 70)  # Set volume 20

def play_track(track=1):
    send_dfplayer_command(0x03, 0x00, track)
    print(f"🎵 Playing Track {track}")

def pause_resume():
    send_dfplayer_command(0x0E)

def volume_up():
    send_dfplayer_command(0x04)

def volume_down():
    send_dfplayer_command(0x05)

# --- Color Helper ---
def color565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

# --- Circle Drawing Helpers ---
def clamp(val, minval, maxval):
    return max(minval, min(maxval, val))

def circle(tft, aPos, aRadius, aColor):
    color_hi = aColor >> 8
    color_lo = aColor & 0xFF
    xend = int(0.7071 * aRadius) + 1
    rsq = aRadius * aRadius
    for x in range(xend):
        y = int(sqrt(rsq - x * x))
        points = [
            (aPos[0] + x, aPos[1] + y),
            (aPos[0] + x, aPos[1] - y),
            (aPos[0] - x, aPos[1] + y),
            (aPos[0] - x, aPos[1] - y),
            (aPos[0] + y, aPos[1] + x),
            (aPos[0] + y, aPos[1] - x),
            (aPos[0] - y, aPos[1] + x),
            (aPos[0] - y, aPos[1] - x),
        ]
        for px, py in points:
            if 0 <= px < tft.width and 0 <= py < tft.height:
                tft._setwindowpoint((px, py))
                tft._writedata(bytearray([color_hi, color_lo]))

def fillcircle(tft, aPos, aRadius, aColor):
    rsq = aRadius * aRadius
    for x in range(aRadius + 1):
        y = int(sqrt(rsq - x * x))
        y0 = clamp(aPos[1] - y, 0, tft.height - 1)
        ey = clamp(aPos[1] + y, 0, tft.height - 1)
        ln = ey - y0 + 1
        tft.vline((aPos[0] + x, y0), ln, aColor)
        tft.vline((aPos[0] - x, y0), ln, aColor)

def draw_play_icon(tft, pos, radius, playing):
    fillcircle(tft, pos, radius, color565(50, 50, 50))
    circle(tft, pos, radius, color565(255, 255, 255))
    if playing:
        w = radius // 3
        h = radius * 2 // 3
        x, y = pos
        tft.fillrect((x - w, y - h//2), (w, h), color565(255,255,255))
        tft.fillrect((x + w//2, y - h//2), (w, h), color565(255,255,255))
    else:
        x, y = pos
        points = [
            (x - radius//3, y - radius//2),
            (x - radius//3, y + radius//2),
            (x + radius//2, y)
        ]
        for py in range(points[0][1], points[1][1]+1):
            px_start = points[0][0] + (py - points[0][1]) * (points[2][0] - points[0][0]) // (points[2][1] - points[0][1]) if (points[2][1] - points[0][1]) != 0 else points[0][0]
            px_end = points[1][0] + (py - points[1][1]) * (points[2][0] - points[1][0]) // (points[2][1] - points[1][1]) if (points[2][1] - points[1][1]) != 0 else points[1][0]
            x_start = min(px_start, px_end)
            x_end = max(px_start, px_end)
            tft.hline((x_start, py), x_end - x_start + 1, color565(255,255,255))

# --- Display .bin Image ---
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

# --- Folder UI ---
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
    {"label": "Videos", "x": 91, "y": 60},
]

selected_index = 0
previous_index = 0
music_mode = False
current_track = 1
images = ["img1.bin", "img2.bin", "img3.bin", "img4.bin"]
image_index = 0
is_playing = True

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
        draw_folder(folders[previous_index]["x"], folders[previous_index]["y"],
                    folders[previous_index]["label"], highlight=False)
    draw_folder(folders[selected_index]["x"], folders[selected_index]["y"],
                folders[selected_index]["label"], highlight=True)
    previous_index = selected_index

def launch_music_mode():
    global music_mode, is_playing
    music_mode = True
    is_playing = True
    tft.fill(BLACK)
    init_dfplayer()
    play_track(current_track)

# --- IR Callback ---

# [same imports and initialization as before, keep unchanged]
# ...
# Add this global flag
power_state = False  # False = OFF, True = ON

# --- IR Callback ---
def ir_callback(data, ctrl):
    global selected_index, previous_index
    global music_mode, current_track, image_index, is_playing
    global power_state

    if data < 0:
        return

    print("IR Code: {:02x}".format(data))

    if data == 0x12:
        power_state = not power_state
        if power_state:
            print("🔛 Power ON")
            music_mode = False
            tft.fill(BLACK)
            display_bin_image("logo.bin")
            time.sleep(2)
            tft.fill(BLACK)
            draw_folders_full()
        else:
            print("🔌 Power OFF")
            music_mode = False
            tft.fill(BLACK)
            display_bin_image("logo.bin")  # Show logo briefly before OFF
            time.sleep(1)
            tft.fill(BLACK)

    elif data == 0x03:
        print("↩️ Back to Folder View")
        music_mode = False
        tft.fill(BLACK)
        draw_folders_full()

    elif data == 0x1E and not music_mode and power_state:
        selected_folder = folders[selected_index]["label"]
        print(f"📂 Selected: {selected_folder}")
        if selected_folder == "Music":
            launch_music_mode()

    elif data == 0x02 and music_mode:
        volume_up()

    elif data == 0x08 and music_mode:
        volume_down()

    elif data == 0x05 and music_mode:
        pause_resume()
        is_playing = not is_playing

    elif data == 0x09 and music_mode:
        current_track += 1
        if current_track > 10:
            current_track = 1
        play_track(current_track)

    elif data == 0x04 and not music_mode and power_state:
        previous_index = selected_index
        selected_index = (selected_index - 1) % len(folders)
        draw_folders_changed()

    elif data == 0x06 and not music_mode and power_state:
        previous_index = selected_index
        selected_index = (selected_index + 1) % len(folders)
        draw_folders_changed()

# [rest of your code continues unchanged...]
# --- IR Setup ---
ir = NEC_16(Pin(35, Pin.IN), ir_callback)

# --- Main Loop ---
tft.fill(BLACK)  # Initial black screen

while True:
    if music_mode:
        display_bin_image(images[image_index])
        image_index = (image_index + 1) % len(images)
        time.sleep(2)
    else:
        time.sleep(0.1)
