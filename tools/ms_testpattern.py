"""
Send test patterns to MS912x USB display adapters.

Sends SMPTE color bars (or other patterns) directly via USB bulk
transfer, bypassing the need for display drivers. Works with the
MS9123 (USB2, CVBS/S-Video) and should work with the MS9132 (USB3).

Usage:
    python ms_testpattern.py [pattern] [mode]

    pattern: bars (default), white, red, green, blue, grid
    mode:    ntsc (default), pal

Requires: pyusb (pip install pyusb) + libusb backend

Frame format (from Linux ms912x DRM driver):
    Header (8 bytes): FF 00, x/16, y(BE16), width/16, height(BE16)
    Pixel data: UYVY (4 bytes per 2 pixels)
    Trailer (8 bytes): FF C0 00 00 00 00 00 00
"""

import struct
import sys
import time
import usb.core
import usb.util


# --- RGB to UYVY conversion (from Linux driver) ---

def rgb_to_yuv(r, g, b):
    y = ((16 << 16) + 16763 * r + 32904 * g + 6391 * b) >> 16
    u = ((128 << 16) - 9676 * r - 18996 * g + 28672 * b) >> 16
    v = ((128 << 16) + 28672 * r - 24009 * g - 4663 * b) >> 16
    return max(0, min(255, y)), max(0, min(255, u)), max(0, min(255, v))


def make_uyvy_line(colors, width):
    """Build one line of UYVY data from a list of (r,g,b) color bars."""
    bar_width = width // len(colors)
    line = bytearray()
    for i in range(0, width, 2):
        # Determine which bar each pixel falls in
        c1 = colors[min(i // bar_width, len(colors) - 1)]
        c2 = colors[min((i + 1) // bar_width, len(colors) - 1)]
        y1, u1, v1 = rgb_to_yuv(*c1)
        y2, u2, v2 = rgb_to_yuv(*c2)
        u = (u1 + u2) // 2
        v = (v1 + v2) // 2
        line.extend([u, y1, v, y2])
    return bytes(line)


# --- Pattern generators ---

BARS_75 = [
    (191, 191, 191),  # White (75%)
    (191, 191, 0),    # Yellow
    (0, 191, 191),    # Cyan
    (0, 191, 0),      # Green
    (191, 0, 191),    # Magenta
    (191, 0, 0),      # Red
    (0, 0, 191),      # Blue
]

# Reverse/castellations row: complement pattern for decoder alignment
BARS_REVERSE = [
    (0, 0, 191),      # Blue
    (0, 0, 0),        # Black
    (191, 0, 191),    # Magenta
    (0, 0, 0),        # Black
    (0, 191, 191),    # Cyan
    (0, 0, 0),        # Black
    (191, 191, 191),  # White (75%)
]


def pattern_bars(width, height):
    """Simple 75% color bars (top section only)."""
    line = make_uyvy_line(BARS_75, width)
    return line * height


def pattern_smpte(width, height):
    """Full SMPTE ECR-1-1978 pattern with three sections."""
    # Section heights: 67% bars, 8% castellations, 25% PLUGE/reference
    h_top = int(height * 0.67)
    h_mid = int(height * 0.08)
    h_bot = height - h_top - h_mid

    data = bytearray()

    # Top 67%: 75% color bars
    top_line = make_uyvy_line(BARS_75, width)
    data.extend(top_line * h_top)

    # Middle 8%: reverse/castellations
    mid_line = make_uyvy_line(BARS_REVERSE, width)
    data.extend(mid_line * h_mid)

    # Bottom 25%: -I, White 100%, +Q, Black with PLUGE
    bar_w = width // 7
    # -I signal (dark desaturated blue)
    i_neg = (0, 34, 102)
    # +Q signal (dark purple)
    q_pos = (50, 0, 106)
    # PLUGE levels
    super_black = (0, 0, 0)       # -4 IRE (below black, clamped)
    black = (16, 16, 16)          # 7.5 IRE setup level
    light_black = (49, 49, 49)    # +4 IRE above setup

    # Build bottom line pixel by pixel (in pairs for UYVY)
    pluge_region = width - 3 * bar_w  # remaining width for PLUGE
    pluge_bar = pluge_region // 4     # divide into 4 equal parts

    bot_colors = []
    for x in range(width):
        if x < bar_w:
            bot_colors.append(i_neg)
        elif x < 2 * bar_w:
            bot_colors.append((255, 255, 255))  # White 100%
        elif x < 3 * bar_w:
            bot_colors.append(q_pos)
        else:
            # PLUGE region: super_black | black | light_black | black
            px = x - 3 * bar_w
            if px < pluge_bar:
                bot_colors.append(super_black)
            elif px < 2 * pluge_bar:
                bot_colors.append(black)
            elif px < 3 * pluge_bar:
                bot_colors.append(light_black)
            else:
                bot_colors.append(black)

    # Convert to UYVY
    bot_line = bytearray()
    for i in range(0, width, 2):
        c1 = bot_colors[i]
        c2 = bot_colors[min(i + 1, width - 1)]
        y1, u1, v1 = rgb_to_yuv(*c1)
        y2, u2, v2 = rgb_to_yuv(*c2)
        u = (u1 + u2) // 2
        v = (v1 + v2) // 2
        bot_line.extend([u, y1, v, y2])

    data.extend(bytes(bot_line) * h_bot)

    return bytes(data)


def pattern_solid(width, height, rgb):
    """Solid color fill."""
    line = make_uyvy_line([rgb], width)
    return line * height


def pattern_pm5544(width, height):
    """Philips PM5544 test card (simplified but recognizable).

    Features: circle with color bars, grayscale, frequency gratings,
    center crosshair, background grid, border castellations.
    """
    import math

    cx, cy = width // 2, height // 2
    # Circle radius: ~85% of half-height to fit 4:3
    radius = int(height * 0.42)
    # Grid: 14 horizontal x 19 vertical lines
    grid_h_spacing = height / 14
    grid_v_spacing = width / 19

    # Background gray level
    bg = (64, 64, 64)
    grid_color = (128, 128, 128)
    white = (191, 191, 191)
    black = (0, 0, 0)

    # EBU 75% color bars
    ebu_bars = [
        (191, 191, 0),    # Yellow
        (0, 191, 191),    # Cyan
        (0, 191, 0),      # Green
        (191, 0, 191),    # Magenta
        (191, 0, 0),      # Red
        (0, 0, 191),      # Blue
    ]

    # Grayscale: 6 levels
    grey_steps = [(i * 191 // 5, i * 191 // 5, i * 191 // 5) for i in range(6)]

    # Circle band boundaries (as fractions of radius from center)
    # Positive = below center, negative = above
    band_top_cast = -0.85     # top castellations
    band_color_top = -0.62    # color bars start
    band_color_bot = -0.35    # color bars end
    band_freq_top = -0.28     # upper frequency gratings
    band_cross_top = -0.12    # center cross zone
    band_cross_bot = 0.12     # center cross zone end
    band_freq_bot = 0.28      # lower frequency gratings end
    band_grey_top = 0.35      # grayscale start
    band_grey_bot = 0.62      # grayscale end
    band_bot_cast = 0.85      # bottom castellations start

    # Build frame pixel by pixel
    pixels = []
    for y in range(height):
        row = []
        dy = (y - cy) / radius  # normalized distance from center

        for x in range(width):
            dx = (x - cx) / radius
            dist = math.sqrt(dx * dx + dy * dy)
            in_circle = dist <= 1.0

            if not in_circle:
                # Outside circle: background with grid
                on_grid = (abs(y % grid_h_spacing) < 1.5 or
                           abs(x % grid_v_spacing) < 1.5)
                # Border castellations (top/bottom edges)
                if y < 16 or y >= height - 16:
                    cast_w = width // 19
                    idx = x // cast_w
                    c = white if idx % 2 == 0 else black
                elif on_grid:
                    c = grid_color
                else:
                    c = bg

            elif abs(dist - 1.0) < 0.015:
                # Circle outline
                c = white

            elif dy < band_top_cast:
                # Above top castellations — inside circle but above content
                c = bg

            elif dy < band_color_top:
                # Top castellations band (B/W square wave)
                cast_w = max(1, int(radius * 0.14))
                idx = (x - cx + radius) // cast_w
                c = white if idx % 2 == 0 else black

            elif dy < band_color_bot:
                # Color bars
                bar_region = x - (cx - int(radius * 0.85))
                bar_total = int(radius * 1.7)
                bar_idx = bar_region * len(ebu_bars) // max(1, bar_total)
                bar_idx = max(0, min(len(ebu_bars) - 1, bar_idx))
                c = ebu_bars[bar_idx]

            elif dy < band_freq_top:
                # Narrow white band separator
                c = white

            elif dy < band_cross_top:
                # Upper frequency gratings
                # Approximate: increasing frequency bands left to right
                section = int((dx + 1.0) * 2.5)  # 0-4
                freq = [4, 8, 16, 24, 32][min(section, 4)]
                c = white if (x // max(1, freq)) % 2 == 0 else black

            elif dy < band_cross_bot:
                # Center crosshair zone
                if abs(dx) < 0.008 or abs(dy) < 0.02:
                    c = white
                elif abs(dx) < 0.15 and abs(dy) < 0.08:
                    c = black
                else:
                    c = bg

            elif dy < band_freq_bot:
                # Lower frequency gratings (reversed)
                section = int((dx + 1.0) * 2.5)
                freq = [32, 24, 16, 8, 4][min(section, 4)]
                c = white if (x // max(1, freq)) % 2 == 0 else black

            elif dy < band_grey_top:
                # Narrow white band separator
                c = white

            elif dy < band_grey_bot:
                # Grayscale staircase
                bar_region = x - (cx - int(radius * 0.85))
                bar_total = int(radius * 1.7)
                bar_idx = bar_region * len(grey_steps) // max(1, bar_total)
                bar_idx = max(0, min(len(grey_steps) - 1, bar_idx))
                c = grey_steps[bar_idx]

            elif dy < band_bot_cast:
                # Bottom castellations (same as top)
                cast_w = max(1, int(radius * 0.14))
                idx = (x - cx + radius) // cast_w
                c = white if idx % 2 == 0 else black

            else:
                c = bg

            row.append(c)

        # Convert row to UYVY
        for i in range(0, width, 2):
            c1 = row[i]
            c2 = row[min(i + 1, width - 1)]
            y1, u1, v1 = rgb_to_yuv(*c1)
            y2, u2, v2 = rgb_to_yuv(*c2)
            u = (u1 + u2) // 2
            v = (v1 + v2) // 2
            pixels.extend([u, y1, v, y2])

    return bytes(pixels)


def pattern_grid(width, height):
    """White grid on black background, 16px spacing."""
    data = bytearray()
    for row in range(height):
        for col in range(0, width, 2):
            if row % 16 == 0 or col % 16 == 0:
                r, g, b = 192, 192, 192
            else:
                r, g, b = 0, 0, 0
            y1, u1, v1 = rgb_to_yuv(r, g, b)
            if (col + 1) % 16 == 0 or row % 16 == 0:
                r2, g2, b2 = 192, 192, 192
            else:
                r2, g2, b2 = 0, 0, 0
            y2, u2, v2 = rgb_to_yuv(r2, g2, b2)
            u = (u1 + u2) // 2
            v = (v1 + v2) // 2
            data.extend([u, y1, v, y2])
    return bytes(data)


# --- Mode definitions (from Linux driver) ---

MODES = {
    "ntsc": {"width": 720, "height": 480, "mode": 0x0200},
    "pal":  {"width": 720, "height": 576, "mode": 0x1100},
    "vga":  {"width": 640, "height": 480, "mode": 0x4000},
    "svga": {"width": 800, "height": 600, "mode": 0x4200},
    "xga":  {"width": 1024, "height": 768, "mode": 0x4700},
}

PIXFMT_UYVY = 0x2200


# --- USB protocol ---

def send_frame(dev, ep, width, height, pixel_data):
    """Send a frame via bulk transfer to endpoint 4."""
    # Header: FF 00, x/16, y(BE16), width/16, height(BE16)
    header = struct.pack(">HBhBh", 0xFF00, 0, 0, width // 16, height)

    # Trailer
    trailer = bytes([0xFF, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    frame = header + pixel_data + trailer
    # Send in chunks (USB bulk max is typically 64KB)
    chunk_size = 65536
    for offset in range(0, len(frame), chunk_size):
        chunk = frame[offset:offset + chunk_size]
        ep.write(chunk)


def main():
    pattern_name = sys.argv[1] if len(sys.argv) > 1 else "bars"
    mode_name = sys.argv[2] if len(sys.argv) > 2 else "ntsc"

    if mode_name not in MODES:
        print(f"Unknown mode: {mode_name} (available: {', '.join(MODES)})")
        sys.exit(1)

    mode = MODES[mode_name]
    w, h = mode["width"], mode["height"]

    # Generate pattern
    print(f"Generating {pattern_name} pattern at {w}x{h} ({mode_name})...")
    if pattern_name == "smpte":
        pixels = pattern_smpte(w, h)
    elif pattern_name == "pm5544":
        pixels = pattern_pm5544(w, h)
    elif pattern_name == "bars":
        pixels = pattern_bars(w, h)
    elif pattern_name == "white":
        pixels = pattern_solid(w, h, (255, 255, 255))
    elif pattern_name == "red":
        pixels = pattern_solid(w, h, (255, 0, 0))
    elif pattern_name == "green":
        pixels = pattern_solid(w, h, (0, 255, 0))
    elif pattern_name == "blue":
        pixels = pattern_solid(w, h, (0, 0, 255))
    elif pattern_name == "grid":
        pixels = pattern_grid(w, h)
    else:
        print(f"Unknown pattern: {pattern_name} (available: smpte, pm5544, bars, white, red, green, blue, grid)")
        sys.exit(1)

    print(f"Frame size: {len(pixels)} bytes pixel data")

    # Find device
    dev = usb.core.find(idVendor=0x534D, idProduct=0x6021)
    if dev is None:
        print("MS9123 not found")
        sys.exit(1)

    # Power on and set resolution via HID
    print(f"Setting mode {mode['mode']:#06x} ({w}x{h})...")
    import hid
    hdev = hid.device()
    hdev.open(0x534D, 0x6021)
    def write_a6_hid(addr, data):
        report = [0x00, 0xA6, addr] + list(data)
        while len(report) < 9:
            report.append(0x00)
        hdev.send_feature_report(report)
        time.sleep(0.05)
    # Power on
    write_a6_hid(0x07, [0x01, 0x02, 0x00, 0x00, 0x00, 0x00])
    time.sleep(0.2)
    # Set resolution
    w_be = [w >> 8, w & 0xFF]
    h_be = [h >> 8, h & 0xFF]
    pf_be = [PIXFMT_UYVY >> 8, PIXFMT_UYVY & 0xFF]
    m_be = [mode["mode"] >> 8, mode["mode"] & 0xFF]
    write_a6_hid(0x04, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    write_a6_hid(0x03, [0x03, 0x00, 0x00, 0x00, 0x00, 0x00])
    write_a6_hid(0x01, w_be + h_be + pf_be)
    write_a6_hid(0x02, m_be + w_be + h_be)
    write_a6_hid(0x04, [0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
    write_a6_hid(0x05, [0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
    hdev.close()
    time.sleep(0.5)

    # Claim vendor interface (interface 3, class 0xFF) for bulk transfer
    try:
        if dev.is_kernel_driver_active(3):
            dev.detach_kernel_driver(3)
    except (NotImplementedError, usb.core.USBError):
        pass

    usb.util.claim_interface(dev, 3)

    # Find bulk OUT endpoint on interface 3
    cfg = dev.get_active_configuration()
    ep_out = None
    for intf in cfg:
        if intf.bInterfaceClass != 0xFF:
            continue
        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT \
               and (ep.bmAttributes & 3) == usb.util.ENDPOINT_TYPE_BULK:
                ep_out = ep
                break

    if ep_out is None:
        print("Bulk OUT endpoint not found")
        sys.exit(1)

    print(f"Sending frame to EP {ep_out.bEndpointAddress:#04x}...")
    send_frame(dev, ep_out, w, h, pixels)
    print("Done!")


if __name__ == "__main__":
    main()
