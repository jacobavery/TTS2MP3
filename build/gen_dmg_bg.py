"""Generate a DMG installer background image (600x360)."""
import struct, zlib, math, os

WIDTH, HEIGHT = 600, 360

def create_bg():
    pixels = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            # Dark gradient background matching app theme
            t = y / HEIGHT
            r = int(18 + 8 * t)
            g = int(14 + 6 * t)
            b = int(32 + 16 * t)

            # Subtle radial glow in center
            cx, cy = WIDTH / 2, HEIGHT * 0.35
            dx, dy = (x - cx) / WIDTH, (y - cy) / HEIGHT
            glow = max(0, 1.0 - math.sqrt(dx * dx + dy * dy) * 2.5)
            glow = glow * glow * 0.3
            r = min(255, int(r + glow * 80))
            g = min(255, int(g + glow * 50))
            b = min(255, int(b + glow * 140))

            # Top text area: "TTS2MP3 Studio" rendered as a subtle horizontal line accent
            if 58 <= y <= 60:
                line_start = WIDTH * 0.3
                line_end = WIDTH * 0.7
                if line_start <= x <= line_end:
                    fade = 1.0 - abs(x - WIDTH / 2) / (WIDTH * 0.2)
                    fade = max(0, min(1, fade))
                    r = min(255, int(r + fade * 60))
                    g = min(255, int(g + fade * 40))
                    b = min(255, int(b + fade * 100))

            # Bottom instruction hint: thin line
            if 308 <= y <= 309:
                line_start = WIDTH * 0.15
                line_end = WIDTH * 0.85
                if line_start <= x <= line_end:
                    fade = 0.15
                    r = min(255, int(r + fade * 100))
                    g = min(255, int(g + fade * 100))
                    b = min(255, int(b + fade * 100))

            # Arrow from app icon area to Applications area
            arrow_y = HEIGHT * 0.56
            if abs(y - arrow_y) < 2:
                arrow_start = WIDTH * 0.35
                arrow_end = WIDTH * 0.65
                if arrow_start <= x <= arrow_end:
                    a_fade = 0.25
                    r = min(255, int(r + a_fade * 120))
                    g = min(255, int(g + a_fade * 100))
                    b = min(255, int(b + a_fade * 200))

            # Arrowhead
            ax = WIDTH * 0.65
            if abs(x - ax) < 10 and abs(y - arrow_y) < abs(x - ax) * 0.8 + 1:
                r = min(255, int(r + 30))
                g = min(255, int(g + 25))
                b = min(255, int(b + 50))

            row.extend([r, g, b])
        pixels.append(bytes(row))

    # Encode as PNG (RGB, no alpha)
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b''
    for row in pixels:
        raw += b'\x00' + row
    png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dmg_background.png')
    with open(out_path, 'wb') as f:
        f.write(png)
    print(f"  DMG background saved: {out_path}")

if __name__ == '__main__':
    create_bg()
