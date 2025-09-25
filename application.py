##!/usr/bin/env python

from app import create_app
from dotenv import load_dotenv

load_dotenv()

# Create the Flask application
application = create_app()
