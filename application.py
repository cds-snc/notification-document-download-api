##!/usr/bin/env python

import os
from app import create_app
from dotenv import load_dotenv
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

load_dotenv()

# Set the XRAY_DAEMON_ADDRESS
os.environ['AWS_XRAY_DAEMON_ADDRESS'] = 'xray-daemon-aws-xray.xray.svc.cluster.local:2000'

# Configure the xray_recorder
xray_recorder.configure(service='notification-document-download-api')

# Create the Flask application
application = create_app()

# Apply the XRayMiddleware directly to the Flask application
XRayMiddleware(application, xray_recorder)

# Run this when the app starts
xray_recorder.begin_segment('AppStart')
application.logger.info('Logger: Application started')
xray_recorder.put_annotation('message', 'Xray: Application started')
xray_recorder.end_segment()
