from enum import Enum

SCAN_VERDICT_TAG = "GuardDutyMalwareScanStatus"


class GuardDutyMalwareS3Verdicts(str, Enum):
    NO_THREATS_FOUND = "NO_THREATS_FOUND"
    THREATS_FOUND = "THREATS_FOUND"
    UNSUPPORTED = "UNSUPPORTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    FAILED = "FAILED"
