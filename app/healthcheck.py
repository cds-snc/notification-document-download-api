from flask import Blueprint
from aws_xray_sdk.core import xray_recorder

healthcheck_blueprint = Blueprint("healthcheck", __name__, url_prefix="")


@healthcheck_blueprint.route("/_status")
def status():
    xray_recorder.begin_segment('HealthCheck')
    xray_recorder.put_annotation('message', 'Xray: Someone hit the healthcheck endpoint')
    xray_recorder.end_segment()
    return "ok", 200
