"""
WSGI config for abrago project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

# -----------------------------------------------------------------------------
# DEPLOYMENT CONFIGURATION (PythonAnywhere)
# -----------------------------------------------------------------------------
# FEATURE: Web Server Gateway Interface (WSGI)
# This file is used by the PythonAnywhere server to communicate with
# the Django application. It serves as the bridge between the live web server
# and our Python code.

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abrago.settings')

application = get_wsgi_application()
