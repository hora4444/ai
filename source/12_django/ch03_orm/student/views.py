from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from student.models import Student
from django.contrib import messages
# Create your views here.
def list(request):
    students = Student.objects.all() # select * from studnet_student
    # return HttpResponse(students)
    return render(request, "student/list.html",{"students":students})

def get(request, id:int):
    # student = Student.objects.get(pk=id)
    # student = get_object_or_404(Student, pk=id)
    # return render(request, "student/get.html", {"student":student})
    try:
        student = Student.objects.get(pk=id)
        return render(request, "student/get.html", {"student":student})
    except Student.DoesNotExist as e:
        # 학생이 존재하지 않는경우
        messages.error(request, f"{id}번 학생을 찾을 수 없습니다.")
        # return redirect("/student")
        return redirect("student:list")
    
def delete(request, id:int):
    student = Student.objects.filter(pk=id)
    if student:
        student.delete()
        messages.success(request,f"{id}번 학생을 삭제하였습니다.")
        return redirect("student:list")
    else:
        # 학생이 존재하지 않는경우
        messages.error(request, f"{id}번 핵생을 찾을 수 없습니다.")
        return redirect("student:list")

from django.http import JsonResponse
from django.forms.models import model_to_dict
def json_test(request):
    # return JsonResponse({"id":4, "name":"hong", "major":"ai"}, json_dumps_params={"ensure_ascii":False})
    studnets = Student.objects.all()
    if studnets:
        studnet = model_to_dict(studnets[0])
        print(studnet)
        return JsonResponse(studnet, json_dumps_params={"ensure_ascii":False})
    return JsonResponse({"data":"없음"}, json_dumps_params={"ensure_ascii":False})