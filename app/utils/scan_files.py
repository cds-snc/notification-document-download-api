from enum import Enum

# from https://github.com/cds-snc/scan-files/blob/630dd2f3c9dfbaae5438d5e2b3a656f0ef057abd/api/models/Scan.py#L16-L23
class ScanVerdicts(Enum):
    IN_PROGRESS = "in_progress"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    ERROR = "error"
    UNKNOWN = "unknown"
    UNABLE_TO_SCAN = "unable_to_scan"