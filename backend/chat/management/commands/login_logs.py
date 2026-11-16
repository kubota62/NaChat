import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from chat.models import Audit


class Command(BaseCommand):
    help = 'Show recent login audit records as JSON Lines (newest first, Japan time).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--account', default='')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 10000:
            raise CommandError('limit must be between 1 and 10000')
        records = Audit.objects.filter(action__in=['login_success', 'login_failed', 'login_rate_limited'])
        if options['account']:
            records = records.filter(details__account=options['account'].strip().lower())
        for row in records.order_by('-created_at', '-pk')[:options['limit']]:
            self.stdout.write(json.dumps({
                'time': timezone.localtime(row.created_at).isoformat(),
                'result': row.action.removeprefix('login_'),
                'user_id': row.actor_id, **row.details,
            }, ensure_ascii=False))
