"""Generate TTS2MP3 Studio app icon as .icns for macOS."""
import subprocess, struct, os, math, tempfile, shutil

# We'll create a simple but professional icon using pure Python + sips/iconutil
# Icon: rounded-rect gradient background with a stylized waveform + play symbol

def create_png(size, path):
    """Create a PNG icon at the given size using raw pixel manipulation."""
    import zlib

    pixels = []
    center_x, center_y = size / 2, size / 2
    radius = size * 0.42  # rounded rect radius
    corner_r = size * 0.18

    for y in range(size):
        row = []
        for x in range(size):
            # Rounded rectangle mask
            dx = max(0, abs(x - center_x) - (radius - corner_r))
            dy = max(0, abs(y - center_y) - (radius - corner_r))
            dist = math.sqrt(dx * dx + dy * dy)
            alpha = max(0, min(255, int((corner_r - dist) * 3 + 1)))

            if alpha > 0:
                # Gradient background: deep purple to indigo
                t = y / size
                r_bg = int(88 * (1 - t) + 30 * t)
                g_bg = int(60 * (1 - t) + 20 * t)
                b_bg = int(220 * (1 - t) + 160 * t)

                # Draw waveform bars
                is_wave = False
                num_bars = 7
                bar_width = size * 0.06
                gap = size * 0.09
                total_w = num_bars * bar_width + (num_bars - 1) * (gap - bar_width)
                start_x = center_x - total_w / 2

                for i in range(num_bars):
                    bx = start_x + i * gap
                    # Varying bar heights (audio waveform pattern)
                    heights = [0.15, 0.28, 0.45, 0.55, 0.40, 0.25, 0.12]
                    bar_h = size * heights[i]
                    bar_top = center_y - bar_h / 2 + size * 0.02
                    bar_bot = center_y + bar_h / 2 + size * 0.02

                    if bx <= x < bx + bar_width and bar_top <= y <= bar_bot:
                        is_wave = True
                        # Brighter gradient on bars
                        bt = (y - bar_top) / max(1, bar_bot - bar_top)
                        r_bg = int(180 + 75 * (1 - bt))
                        g_bg = int(140 + 80 * (1 - bt))
                        b_bg = 255
                        break

                # Draw play triangle (small, top-left area)
                tri_cx = size * 0.22
                tri_cy = size * 0.22
                tri_size = size * 0.10
                # Simple play triangle check
                tx = x - tri_cx
                ty = y - tri_cy
                if abs(ty) < tri_size * 0.6:
                    right_edge = tri_size * 0.5 - abs(ty) * 0.7
                    left_edge = -tri_size * 0.3
                    if left_edge <= tx <= right_edge:
                        r_bg, g_bg, b_bg = 255, 255, 255

                # "MP3" text indicator - small dots at bottom
                dot_y_pos = size * 0.78
                if abs(y - dot_y_pos) < size * 0.015:
                    for di in range(3):
                        dot_x = center_x + (di - 1) * size * 0.06
                        if (x - dot_x) ** 2 + (y - dot_y_pos) ** 2 < (size * 0.012) ** 2:
                            r_bg, g_bg, b_bg = 255, 255, 255

                row.extend([r_bg, g_bg, b_bg, alpha])
            else:
                row.extend([0, 0, 0, 0])
        pixels.append(bytes(row))

    # Encode as PNG
    def make_png(width, height, rows):
        def chunk(ctype, data):
            c = ctype + data
            return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

        sig = b'\x89PNG\r\n\x1a\n'
        ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
        raw = b''
        for row in rows:
            raw += b'\x00' + row
        return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')

    with open(path, 'wb') as f:
        f.write(make_png(size, size, pixels))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    iconset_dir = os.path.join(script_dir, 'TTS2MP3.iconset')
    os.makedirs(iconset_dir, exist_ok=True)

    # macOS iconset requires these specific sizes
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        print(f"  Generating {s}x{s}...")
        fname = f"icon_{s}x{s}.png"
        create_png(s, os.path.join(iconset_dir, fname))
        # Also create @2x variants
        if s <= 512:
            # For iconset naming convention
            pass

    # Rename to match iconset convention
    renames = {
        'icon_16x16.png': 'icon_16x16.png',
        'icon_32x32.png': 'icon_16x16@2x.png',
        'icon_32x32.png': 'icon_32x32.png',
        'icon_64x64.png': 'icon_32x32@2x.png',
        'icon_128x128.png': 'icon_128x128.png',
        'icon_256x256.png': 'icon_128x128@2x.png',
        'icon_256x256.png': 'icon_256x256.png',
        'icon_512x512.png': 'icon_256x256@2x.png',
        'icon_512x512.png': 'icon_512x512.png',
        'icon_1024x1024.png': 'icon_512x512@2x.png',
    }

    # Generate all needed sizes and copy to proper names
    needed = {
        'icon_16x16.png': 16,
        'icon_16x16@2x.png': 32,
        'icon_32x32.png': 32,
        'icon_32x32@2x.png': 64,
        'icon_128x128.png': 128,
        'icon_128x128@2x.png': 256,
        'icon_256x256.png': 256,
        'icon_256x256@2x.png': 512,
        'icon_512x512.png': 512,
        'icon_512x512@2x.png': 1024,
    }

    # Clear and regenerate with proper names
    shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir)

    generated = {}
    for name, s in needed.items():
        if s not in generated:
            print(f"  Generating {s}x{s}...")
            tmp = os.path.join(iconset_dir, f'tmp_{s}.png')
            create_png(s, tmp)
            generated[s] = tmp
        shutil.copy2(generated[s], os.path.join(iconset_dir, name))

    # Clean up temp files
    for f in generated.values():
        if os.path.exists(f):
            os.remove(f)

    # Convert to .icns using iconutil
    icns_path = os.path.join(script_dir, 'TTS2MP3.icns')
    print(f"  Creating {icns_path}...")
    subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', icns_path], check=True)
    print(f"  Done! Icon saved to {icns_path}")

    # Cleanup iconset
    shutil.rmtree(iconset_dir)

if __name__ == '__main__':
    main()
