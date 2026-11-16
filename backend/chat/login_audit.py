import ipaddress
from .models import Audit


def connection_ip(request):
    # Only nginx is exposed; it overwrites X-Real-IP with its peer address.
    value = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ''


def record_login(request, account, result, user=None):
    Audit.objects.create(
        actor=user, action='login_' + result, target=str(user.pk) if user else '',
        details={
            'account': account[:254],
            'email': user.email if user else '',
            'display_name': user.display_name if user else '',
            'ip': connection_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:512],
        },
    )
