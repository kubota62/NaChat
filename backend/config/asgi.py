import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from django.core.asgi import get_asgi_application
http=get_asgi_application()
from django.conf import settings
from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import OriginValidator
from chat.consumers import Updates
application=ProtocolTypeRouter({'http':http,'websocket':OriginValidator(AuthMiddlewareStack(URLRouter([path('ws',Updates.as_asgi())])),settings.CSRF_TRUSTED_ORIGINS)})
