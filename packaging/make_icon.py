"""Convert static/img/logo.png into the platform icon artifacts used by the build:

  star.ico          Windows exe / Inno Setup installer
  star.png          Linux AppImage (square, 512x512)
  star.iconset/     macOS iconset (iconutil -c icns star.iconset -> star.icns)

构建期脚本（CI 与 build_windows.bat 共用），需要 pillow。
位图母版是 static/img/logo.png（1024x1024 RGBA），矢量源是同目录 logo.svg，
改版时先由 SVG 重新导出母版（如 qlmanage -t -s 1024 / rsvg-convert），再跑本脚本。
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'static', 'img', 'logo.png')


def main():
    img = Image.open(SRC).convert('RGBA')

    # Windows .ico (multi-size)
    img.save(os.path.join(HERE, 'star.ico'),
             sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

    # Linux AppImage square PNG
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, 'star.png'))

    # macOS .icns via iconset (iconutil is macOS-only; skipped elsewhere)
    if __import__('sys').platform == 'darwin':
        iconset = os.path.join(HERE, 'star.iconset')
        os.makedirs(iconset, exist_ok=True)
        # Apple iconset spec: 16/32/128/256/512 px, each with an @2x retina
        # variant (512@2x = 1024, exactly the master's size)
        for size in (16, 32, 128, 256, 512):
            img.resize((size, size), Image.LANCZOS).save(
                os.path.join(iconset, f'icon_{size}x{size}.png'))
            img.resize((size * 2, size * 2), Image.LANCZOS).save(
                os.path.join(iconset, f'icon_{size}x{size}@2x.png'))

    print('icons written:', HERE)


if __name__ == '__main__':
    main()
