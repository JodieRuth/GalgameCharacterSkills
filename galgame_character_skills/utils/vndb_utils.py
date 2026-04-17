import base64
import json
import os


def load_r18_traits(base_dir):
    try:
        json_path = os.path.join(base_dir, 'utils', 'r18_traits.json')
        if not os.path.exists(json_path):
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r18_traits.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        encoded_traits = data.get('encoded_traits', [])
        return {base64.b64decode(t.encode()).decode('utf-8') for t in encoded_traits}
    except Exception as e:
        print(f"Warning: Failed to load r18_traits: {e}")
        return set()


def clean_vndb_data(vndb_data):
    if vndb_data and isinstance(vndb_data, dict):
        cleaned = vndb_data.copy()
        cleaned.pop('image_url', None)
        return cleaned
    return vndb_data
