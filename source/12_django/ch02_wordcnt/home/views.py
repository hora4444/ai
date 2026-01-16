from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

# Create your views here.
def index(requests):
    context = {"msg":"wordCount Welcome Page",
                "greeting":"Hellom Django(장고)"}
    return render(request=requests,
                    template_name="home/index.html",
                    context=context)

def test(requests:HttpRequest) -> HttpResponse:
    return HttpResponse("""<h1>TEST PAGE</h1>
                        <button onclick="location.href='/'">뒤로가기</button>
                        """)

def showIntId(request:HttpRequest, id:int) -> HttpResponse:
    msg = f"숫자 ID는 {id}"
    id_type ='"int"입니다.'
    return render(request,
                    "home/showId.html",
                    {"msg":msg, "type":id_type})

def showStrId(request:HttpRequest, id:str) -> HttpResponse:
    msg = f"문자 ID는 {id}"
    id_type ='"str"입니다.'
    return render(request,
                    "home/showId.html",
                    {"msg":msg, "type":id_type})
