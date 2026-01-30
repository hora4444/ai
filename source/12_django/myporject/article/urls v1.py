from django.urls import path
from . import views
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from .models import Article
from django.urls import reverse_lazy
'''
기사 목록 /article/          article:list
기사 추가 /article/new/      article:new
기사 상세 /article/1/detail  article:detail
기사 수정 /article/1/edit/   article:edit
기사 삭제 /article/1/delete/ boarticleok:delete
'''
app_name="article"
urlpatterns = [
    # path("", views.article_list, name="list"),
    # path("new/", views.article_new, name="new"),
    # path("<int:pk>/detail/", views.article_detail, name="detail"),
    # path("<int:pk>/edit/", views.article_edit, name="edit"),
    # path("<int:pk>/delete/", views.article_delete, name="delete"),

    # 이렇게 쓰면 views.py도 필요가 없으나 검색 기능을 사용하려면 변경이 필요함 
    path("", ListView.as_view(model=Article, paginate_by=3), name="list"),
    path("new/", CreateView.as_view(model=Article, fields="__all__"), name="new"),
    path("<int:pk>/detail/",  DetailView.as_view(model=Article), name="detail"),
    path("<int:pk>/edit/", UpdateView.as_view(model=Article, fields="__all__"), name="edit"),
    path("<int:pk>/delete/", DeleteView.as_view(model=Article, success_url=reverse_lazy("article:list")), name="delete"),
]