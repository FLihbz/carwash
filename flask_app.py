#!/usr/bin/env python3
import os
import sys
from wsgiref.handlers import CGIHandler

# Add your project directory to the sys.path
project_home = '/home/flibz/CARWASH'
if project_home not in sys.path:
    sys.path.append(project_home)

# Activate your virtual environment
activate_this = os.path.join(project_home, 'venv/bin/activate_this.py')
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Import your Flask app
from app import app as application  # Replace 'app' with the correct name of your Flask app module

if __name__ == "__main__":
    CGIHandler().run(application)
