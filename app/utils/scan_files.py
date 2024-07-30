import json
from enum import Enum

import requests
from flask import current_app


# from https://github.com/cds-snc/scan-files/blob/630dd2f3c9dfbaae5438d5e2b3a656f0ef057abd/api/models/Scan.py#L16-L23
class ScanVerdicts(Enum):
    IN_PROGRESS = "in_progress"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    ERROR = "error"
    UNKNOWN = "unknown"
    UNABLE_TO_SCAN = "unable_to_scan"


def get_scan_verdict(file_content, mimetype) -> ScanVerdicts:
    resp = requests.post(
        f"{current_app.config['ANTIVIRUS_API_HOST']}/clamav",
        files={"file": ("uploaded_file", file_content, mimetype)},
        headers={"Authorization": current_app.config["ANTIVIRUS_API_KEY"]},
    )
    data = json.loads(resp.text)
    try:
        return ScanVerdicts(data["verdict"])
    except ValueError:
        raise Exception("Unknown scan value")
