# wordcnt 패키지 안의 urls 모듈
# wordcnt/          : name=wordcnt:wordinput
# wordcnt/about/    : name=wordcnt:abount
# wordcnt/result/   : name=wordcnt:result
from django.urls import path
from wordcnt.views import wordinput, about, result
app_name="wordcnt"
urlpatterns = [
    path("", wordinput, name="wordinput"), # /wordcnt/단어입력 받는 페이지
    path("about/", about, name="about"), # name=wordcnt:abount
    path("result/", result, name="result"), # name=wordcnt:result
]