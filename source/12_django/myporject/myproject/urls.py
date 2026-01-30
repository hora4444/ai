"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", lambda request :redirect("file:upload_file")), # 루트경로 접속시 파일업로드 페이지로 이동
    path("blog/", include("blog.urls")),
    path("book/", include("book.urls")),
    path("article/", include("article.urls")),
    path("file/", include("filetest.urls")),
]
# 장고는 static은 자동연결, media는 개발자가 url과 root 경로를 수동연결
from django.conf.urls.static import static
import os
from . import settings

urlpatterns += static(settings.MEDIA_URL, # /media/
                    document_root=settings.MEDIA_ROOT) # BASE_DIR/_media 저장

