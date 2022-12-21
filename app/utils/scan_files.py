from enum import Enum

class ScanVerdicts(Enum):
    IN_PROGRESS = "in_progress"
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    ERROR = "error"
    UNKNOWN = "unknown"
    UNABLE_TO_SCAN = "unable_to_scan"