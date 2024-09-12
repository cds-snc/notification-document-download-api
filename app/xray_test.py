from aws_xray_sdk.core import xray_recorder
from flask import Blueprint, current_app

xray_blueprint = Blueprint("xray", __name__, url_prefix="")


@xray_blueprint.route("/_debug")
def status():
    # Retrieve the current X-Ray segment
    segment = xray_recorder.current_segment()
    # Get the trace ID from the current segment
    trace_id = segment.trace_id if segment else "No segment"
    # Log the trace ID
    current_app.logger.info(f"Responding to request with X-Ray trace ID: {trace_id}")
    current_app.logger.info("Xray Check Called")
    return "Xray OK!", 200
