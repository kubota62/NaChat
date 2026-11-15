from django.urls import path
from chat import views as v
urlpatterns=[path('api/'+route,view) for route,view in [('health',v.health),('csrf',v.csrf),('login',v.sign_in),('logout',v.sign_out),('me',v.me),('password',v.password),('users',v.users),('users/<int:pk>',v.manage_user),('rooms',v.rooms),('rooms/<int:pk>/members',v.members),('rooms/<int:pk>/messages',v.room_messages),('rooms/<int:pk>/changes',v.changes),('rooms/<int:pk>/read',v.read),('messages/<int:pk>',v.message),('messages/<int:pk>/reaction',v.reaction),('search',v.search),('attachments/<int:pk>',v.attachment)]]
