from django.core.management.base import BaseCommand, CommandError
from chat.models import User, Room, Membership

class Command(BaseCommand):
    help='Create the first administrator (login ID/password: administorator)'
    def handle(self,*args,**options):
        if User.objects.exists(): raise CommandError('Users already exist. Use createsuperuser or changepassword.')
        user=User.objects.create_superuser('admin@nachat.local','administorator',display_name='管理者')
        for title,description in [('全社アナウンス','全社のお知らせや大切な共有はこちらへ。'),('雑談','仕事の合間のひと息に。気軽に話しましょう。'),('ヘルプ・相談','困ったときは、チームの力を借りよう。')]:
            room=Room.objects.create(name=title,description=description,owner=user)
            Membership.objects.create(room=room,user=user)
        self.stdout.write(self.style.SUCCESS('Administrator and starter channels created. Login ID/password: administorator'))
