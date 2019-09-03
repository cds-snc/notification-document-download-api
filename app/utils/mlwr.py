import os
import uuid
from assemblyline_client import Client
from flask import current_app


def upload_to_mlwr(file):
    client = Client(
        current_app.config["MLWR_HOST"],
        apikey=(
            current_app.config["MLWR_USER"],
            current_app.config["MLWR_HOST"]))
    resp = client.submit(contents=file, fname=str(uuid.uuid4()))
    return resp["submission"]["sid"]
