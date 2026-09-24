"""Generate the AccessibleIDE app icon (.ico).

High-contrast, dyslexia-friendly: bold dark "A" on a rounded
accent-yellow tile. Produces multi-size ICO for Windows.
"""
from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 24, 32, 48, 64, 128, 256]
BG = (255, 217, 61, 255)      # accent yellow #FFD93D
FG = (13, 13, 13, 255)        # near-black #0D0D0D
RADIUS_RATIO = 0.22


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded square background
    radius = max(1, int(size * RADIUS_RATIO))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    # Bold "A" letter
    font_size = int(size * 0.72)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "A"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1] - int(size * 0.02)
    d.text((x, y), text, font=font, fill=FG)
    return img


if __name__ == "__main__":
    images = [draw_icon(s) for s in SIZES]
    images[-1].save(
        "src/accessible_ide/assets/icon.ico",
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[:-1],
    )
    print("icon.ico written")