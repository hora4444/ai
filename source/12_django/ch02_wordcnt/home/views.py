from django.shortcuts import render

# Create your views here.
def index(requests):
    context = {"meg":"wordCount Welcome Page",
                "greeting":"Hellom Django(장고)"}
    return render(request=requests,
                    template_name="home/index.html",
                    context=context)