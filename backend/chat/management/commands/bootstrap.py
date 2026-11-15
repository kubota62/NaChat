import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from chat.models import User, Room, Membership

class Command(BaseCommand):
    help='Create the first administrator interactively (no password in command history)'
    def handle(self,*args,**options):
        if User.objects.exists(): raise CommandError('Users already exist. Use createsuperuser or changepassword.')
        email=input('Administrator email: ').strip().lower()
        from django.core.validators import validate_email
        validate_email(email)
        name=input('Display name: ').strip() or '管理者'
        password=getpass.getpass('Initial password (12+ characters): ')
        validate_password(password,User(email=email,display_name=name))
        if password!=getpass.getpass('Repeat password: '): raise CommandError('Passwords do not match')
        user=User.objects.create_superuser(email,password,display_name=name)
        for title,description in [('全社アナウンス','全社のお知らせや大切な共有はこちらへ。'),('雑談','仕事の合間のひと息に。気軽に話しましょう。'),('ヘルプ・相談','困ったときは、チームの力を借りよう。')]:
            room=Room.objects.create(name=title,description=description,owner=user)
            Membership.objects.create(room=room,user=user)
        self.stdout.write(self.style.SUCCESS('Administrator and starter channels created.'))
