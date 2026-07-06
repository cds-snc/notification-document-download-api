from urllib.parse import quote, urlencode, urlunsplit

from flask import current_app, url_for
from notifications_utils.base64_uuid import bytes_to_base64, uuid_to_base64


def get_direct_file_url(service_id, document_id, key, sending_method):
    return url_for(
        "download.download_document",
        service_id=service_id,
        document_id=document_id,
        key=bytes_to_base64(key) if key else "",
        sending_method=sending_method,
        _external=True,
    )


def get_api_download_url(service_id, document_id, key, filename):
    scheme = current_app.config["HTTP_SCHEME"]
    netloc = current_app.config["BACKEND_HOSTNAME"]
    path = "d/{}/{}".format(uuid_to_base64(service_id), uuid_to_base64(document_id))
    query_params = {}
    if key:
        query_params["key"] = bytes_to_base64(key)
    if filename:
        query_params["filename"] = filename
    query = urlencode(query_params, quote_via=quote)

    return urlunsplit([scheme, netloc, path, query, None])
