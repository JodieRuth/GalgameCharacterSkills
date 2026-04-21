"""角色卡图片工具模块，负责下载角色图并将 JSON 嵌入 PNG。"""

import base64
import json
import zlib

import requests


def download_vndb_image(image_url, output_path):
    if not image_url:
        return False
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Failed to download image: {e}")
    return False


def embed_json_in_png(json_data, png_path, output_png_path):
    try:
        with open(png_path, 'rb') as f:
            png_data = f.read()

        if png_data[:8] != b'\x89PNG\r\n\x1a\n':
            print("Invalid PNG signature")
            return False

        json_str = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        json_base64 = base64.b64encode(json_bytes).decode('ascii')
        text_data = b'chara\x00' + json_base64.encode('ascii')

        crc = zlib.crc32(b'tEXt' + text_data) & 0xffffffff

        tex_chunk = (
            len(text_data).to_bytes(4, 'big') +
            b'tEXt' +
            text_data +
            crc.to_bytes(4, 'big')
        )

        chunks = []
        pos = 8

        while pos < len(png_data):
            if pos + 8 > len(png_data):
                break

            length = int.from_bytes(png_data[pos:pos+4], 'big')
            chunk_type = png_data[pos+4:pos+8]

            if pos + 12 + length > len(png_data):
                break

            chunk_data = png_data[pos:pos+12+length]
            chunks.append((chunk_type, chunk_data))

            pos += 12 + length

        new_png = png_data[:8]
        tex_inserted = False

        for chunk_type, chunk_data in chunks:
            if chunk_type == b'IDAT' and not tex_inserted:
                new_png += tex_chunk
                tex_inserted = True
            new_png += chunk_data

        if not tex_inserted:
            new_png += tex_chunk

        with open(output_png_path, 'wb') as f:
            f.write(new_png)

        print(f"Successfully embedded JSON into PNG: {output_png_path}")
        return True

    except Exception as e:
        print(f"Failed to embed JSON in PNG: {e}")
        import traceback
        traceback.print_exc()
        return False
