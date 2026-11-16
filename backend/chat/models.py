import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self, email, password=None, **extra):
        return self.create_user(email,password,is_staff=True,is_superuser=True,**extra)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=80)
    avatar = models.FileField(upload_to="avatars/", blank=True)
    must_change_password = models.BooleanField(default=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['display_name']
    objects = UserManager()
    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

class Room(models.Model):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=12, default='public')
    dm_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    members = models.ManyToManyField(User, through='Membership', related_name='rooms')
    sequence = models.BigIntegerField(default=0)
    version = models.BigIntegerField(default=0)

class Membership(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_sequence = models.BigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['room','user'],name='unique_member')]

class Message(models.Model):
    room = models.ForeignKey(Room,on_delete=models.CASCADE)
    author = models.ForeignKey(User,on_delete=models.PROTECT)
    client_id = models.UUIDField(default=uuid.uuid4)
    sequence = models.BigIntegerField()
    parent = models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='replies')
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True)
    deleted = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['room','sequence'],name='unique_sequence'),models.UniqueConstraint(fields=['author','client_id'],name='unique_submission')]
        indexes = [models.Index(fields=['room','parent','sequence'])]

class ThreadRead(models.Model):
    parent = models.ForeignKey(Message,on_delete=models.CASCADE)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    sequence = models.BigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['parent','user'],name='unique_thread_read')]

class Reaction(models.Model):
    message = models.ForeignKey(Message,on_delete=models.CASCADE,related_name='reactions')
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    emoji = models.CharField(max_length=16)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['message','user','emoji'],name='unique_reaction')]

class Change(models.Model):
    room = models.ForeignKey(Room,on_delete=models.CASCADE)
    version = models.BigIntegerField()
    message = models.ForeignKey(Message,on_delete=models.CASCADE)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['room','version'],name='unique_change')]

def attachment_path(instance, filename):
    return f'files/{uuid.uuid4().hex}'

class Attachment(models.Model):
    message = models.ForeignKey(Message,on_delete=models.CASCADE,related_name='attachments')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=attachment_path)
    size = models.BigIntegerField()

class Audit(models.Model):
    details = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(User,null=True,on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
