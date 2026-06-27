"""
WSGI config for abrago project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

# -----------------------------------------------------------------------------
# CONFIGURATION DE DÉPLOIEMENT (PythonAnywhere)
# -----------------------------------------------------------------------------
# FONCTIONNALITÉ : Web Server Gateway Interface (WSGI)
# Fichier utilisé par le serveur PythonAnywhere pour communiquer avec
# l'application Django. Fait le pont entre le serveur web en direct et le code Python.

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abrago.settings')

application = get_wsgi_application()
