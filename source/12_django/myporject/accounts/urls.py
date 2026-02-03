from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from . import views

LANGUAGE_CODE = "ko-kr"

'''
accounts.urls - 모든앱을 통틀어 하나밖에 없는 기능이라 app_name을 안 만듦
/accounts/singup/  -> (회원가입 - singup)
/accounts/login/   -> (로그인 - login)
/accounts/profile/ -> (회원정보보기 - profile)
/accounts/logout/  -> (로그아웃 - logout)
'''
urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.custom_login, name="login"),
    path("profile/", views.profile, name="profile"),
    path("logout/", views.logout, name="logout"),
]