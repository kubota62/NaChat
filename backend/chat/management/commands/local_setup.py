import secrets
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from chat.models import User,Room,Membership

class Command(BaseCommand):
    help='Initialize an empty local trial and save credentials to the mounted /bootstrap directory.'
    def handle(self,*args,**options):
        if User.objects.exists(): raise CommandError('Refusing to overwrite existing users')
        password='administorator'
        user=User.objects.create_superuser('admin@nachat.local',password,display_name='管理者')
        for name,desc in [('全社アナウンス','全社のお知らせや大切な共有はこちらへ。'),('雑談','仕事の合間のひと息に。気軽に話しましょう。'),('ヘルプ・相談','困ったときは、チームの力を借りよう。')]:
            room=Room.objects.create(name=name,description=desc,owner=user)
            Membership.objects.create(room=room,user=user)
        Path('/bootstrap/初回ログイン.txt').write_text(f'URL: http://localhost:8080\nログインID: administorator\n初期パスワード: {password}\nパスワード変更は任意です。設定画面から変更できます。\n',encoding='utf-8')
        self.stdout.write('Local administrator initialized. Credentials saved to .local/初回ログイン.txt')
