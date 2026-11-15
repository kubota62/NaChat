from django.http import JsonResponse

class AccountGuard:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        if request.user.is_authenticated and request.user.must_change_password and request.path not in ['/api/me','/api/password','/api/logout','/api/csrf']:
            return JsonResponse({'error':'最初にパスワードを変更してください。'},status=403)
        return self.get_response(request)
