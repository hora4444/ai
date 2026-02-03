from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(verbose_name="전화", max_length=20)
    address      = models.CharField(verbose_name="주소", max_length=100)
    def __str__(self):
        return "{}({}-{})".format(self.user.username, self.phone_number, self.address)

# 이벤트처리 : profile insert시 가입인사 메일을 전송 => signals(post_save)
from django.db.models.signals import post_save
from django.core.mail import send_mail
from myproject.settings import EMAIL_HOST_USER
def on_send_mail(sender, **kwargs):
    # print(kwargs)
    if kwargs["created"]:
        user = kwargs["instance"].user
        if not user.email:
            print("메일 주소가 없어서 메일을 보낼 수 없습니다.")
            return
        subject = user.username + "님 회원가입을 환영합니다."
        body = user.username + "님 회원가입을 진심으로 환영합니다. 즐거운 시간 되세요."
        bodyHtml = """<h1>{}님 가입 감사합니다.</h1>
        <h2>즐거운 시간 되세요</h2>
        <img src="https://cdn.crowdpic.net/detail-thumb/thumb_d_9DF9B17D0C251E7C9A0764994BBEFBBC.jpg" alt="Django"/>""".format(user.username)
        # setting.py에 smtp 셋팅
        send_mail(
            subject=subject,
            message=body,
            from_email=EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=bodyHtml,
            fail_silently=False, # 메일 전송이 안 되었을 때, 아무일도 하지 않음
        )
post_save.connect(on_send_mail, sender=Profile) # Profile 모델의 DB저장 후에 on_send_mail 함수 실행