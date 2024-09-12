##!/usr/bin/env python

from app import create_app
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configure the xray_recorder
xray_recorder.configure(service="notification-document-download-api")

# Create the Flask application
application = create_app()

# Apply the XRayMiddleware directly to the Flask application
XRayMiddleware(application, xray_recorder)

# Retrieve the current X-Ray segment
segment = xray_recorder.current_segment()
# Get the trace ID from the current segment
trace_id = segment.trace_id if segment else "No segment"
# Log the trace ID
application.logger.info(f"Responding to request with X-Ray trace ID: {trace_id}")
