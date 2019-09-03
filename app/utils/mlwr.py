import os
import uuid
from assemblyline_client import Client

def upload_to_mlwr(file):
    client = Client(
        os.getenv("MLWR_HOST"),
        apikey=(
            os.getenv("MLWR_USER") , 
            os.getenv("MLWR_KEY") ))
    resp = client.submit(contents=file,fname=str(uuid.uuid4()))
    return resp["submission"]["sid"]