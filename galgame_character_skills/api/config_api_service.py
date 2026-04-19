from ..domain import ok_result


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 6:
        return "*" * len(secret)
    return f"{secret[:3]}***{secret[-2:]}"


def get_config_result(get_app_settings):
    settings = get_app_settings()
    return ok_result(
        baseurl=settings.baseurl,
        modelname=settings.modelname,
        max_retries=settings.max_retries,
        workspace_dir=settings.workspace_dir,
        has_apikey=bool(settings.apikey),
        apikey_masked=_mask_secret(settings.apikey),
    )


__all__ = ["get_config_result"]
