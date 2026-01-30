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
    path("", views.ArticleListView.as_view(), name="list"),
    path("new/", views.ArticleCreateView.as_view(), name="new"),
    path("<int:pk>/detail/", views.ArticleDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ArticleUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ArticleDeleteView.as_view(), name="delete"),
]