"""VNDB 网关模块，封装对 VNDB HTTP 接口的访问实现。"""

import requests
from requests import Response


class VndbGateway:
    def query_character(self, char_id: str, timeout: int = 10) -> Response:
        """查询 VNDB 角色信息。

        Args:
            char_id: 角色编号。
            timeout: 请求超时时间。

        Returns:
            Response: HTTP 响应对象。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultVndbGateway(VndbGateway):
    def __init__(self, endpoint: str = "https://api.vndb.org/kana/character") -> None:
        """初始化默认 VNDB 网关。

        Args:
            endpoint: VNDB 接口地址。

        Returns:
            None

        Raises:
            Exception: 初始化失败时向上抛出。
        """
        self.endpoint = endpoint

    def query_character(self, char_id: str, timeout: int = 10) -> Response:
        """查询 VNDB 角色信息。

        Args:
            char_id: 角色编号。
            timeout: 请求超时时间。

        Returns:
            Response: HTTP 响应对象。

        Raises:
            TimeoutError: 请求超时时抛出。
            Exception: 请求失败时向上抛出。
        """
        api_request = {
            "filters": ["id", "=", f"c{char_id}"],
            "fields": "id,name,original,aliases,description,age,birthday,blood_type,height,weight,bust,waist,hips,image.url,traits.name,vns.title,sex",
        }
        try:
            response = requests.post(self.endpoint, json=api_request, timeout=timeout)
            return response
        except requests.exceptions.Timeout as e:
            raise TimeoutError("VNDB API timeout") from e


__all__ = ["VndbGateway", "DefaultVndbGateway"]
