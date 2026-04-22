"""根路径路由注册模块。"""

from flask import render_template


def register_root_routes(app) -> None:
    """注册根路径路由。"""

    @app.route("/")
    def index():
        """返回前端首页模板。

        Args:
            None

        Returns:
            str: 渲染后的首页 HTML。

        Raises:
            Exception: 模板渲染失败时向上抛出。
        """
        return render_template("index.html")


__all__ = ["register_root_routes"]
