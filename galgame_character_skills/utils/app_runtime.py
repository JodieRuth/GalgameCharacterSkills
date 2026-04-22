"""应用运行时工具模块，提供日志配置与浏览器自动打开等辅助能力。"""

import logging
import time
import webbrowser


class NoRequestFilter:
    def filter(self, record):
        return not (record.getMessage().startswith('127.0.0.1') and 'HTTP' in record.getMessage())


def configure_werkzeug_logging():
    log = logging.getLogger('werkzeug')
    log.addFilter(NoRequestFilter())


def open_browser(url='http://127.0.0.1:5000', delay_seconds=0.5):
    time.sleep(delay_seconds)
    webbrowser.open(url)
