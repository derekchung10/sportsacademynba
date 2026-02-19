"""WSGI config for Academy Outreach Platform."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academy_outreach.settings')
application = get_wsgi_application()
