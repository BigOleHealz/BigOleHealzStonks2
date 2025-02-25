from typing import Literal


def create_permission_url(
    owner_type: Literal["Organization", "User"], owner_name: str, installation_id: int
):
    url_base = "https://github.com"
    url_part = f"settings/installations/{installation_id}/permissions/update"
    if owner_type == "Organization":
        return f"{url_base}/organizations/{owner_name}/{url_part}"
    return f"{url_base}/{url_part}"
