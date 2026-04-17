def build_llm_config(data):
    return {
        'baseurl': data.get('baseurl', ''),
        'modelname': data.get('modelname', ''),
        'apikey': data.get('apikey', ''),
        'max_retries': data.get('max_retries', 0) or None
    }
