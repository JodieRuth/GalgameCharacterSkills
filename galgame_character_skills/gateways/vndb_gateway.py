import requests


class VndbGateway:
    def query_character(self, char_id, timeout=10):
        raise NotImplementedError


class DefaultVndbGateway(VndbGateway):
    def __init__(self, endpoint="https://api.vndb.org/kana/character"):
        self.endpoint = endpoint

    def query_character(self, char_id, timeout=10):
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
