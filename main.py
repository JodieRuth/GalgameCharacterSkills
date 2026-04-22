import threading

from galgame_character_skills import create_app, open_browser


if __name__ == '__main__':
    app = create_app()
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
