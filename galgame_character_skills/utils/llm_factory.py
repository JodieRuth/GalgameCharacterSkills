from .llm_interaction import LLMInteraction


def build_llm_client(config=None):
    config = config or {}
    baseurl = config.get('baseurl', '')
    modelname = config.get('modelname', '')
    apikey = config.get('apikey', '')
    max_retries = config.get('max_retries', 0) or None
    client = LLMInteraction()
    if baseurl or modelname or apikey:
        client.set_config(baseurl, modelname, apikey, max_retries=max_retries)
    return client
