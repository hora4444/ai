from django.shortcuts import render
from django.http import HttpResponse
from pyexpat.errors import messages


# Create your views here.
def home(request):
    # return HttpResponse("<h1>Hello World</h1>")
    return render(request, template_name="home.html", context={"msg":"Django(장고)"})
