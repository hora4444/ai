from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from .models import Book
from .forms import BookModelForm
# 1. form없이 사용 2. form객체생성후(6장) 3. DjangoGenericView 이용 4. GenericView상속(7장)
# def book_list(request):
#     return render(request, "book/book_list.html",{"book_list":Book.objects.all()})
book_list = ListView.as_view(model=Book)

# book_new = CreateView.as_view(model=Book,
#                             fields=['title','author','publisher','sales'])
def book_new1(request):
    # GET : template(book/book_form.html) 페이지로 응답
    # POST : 파라미터 변수받아 유효성 체크
        # 1) success => db에 save() -> book:list로
        # 2) fail => 오류메세지와 함꼐 입력베이지로 이동(form 객체 활용)
    if request.method == "POST":
        # 파라미터 받아 ip까지 입력한 후 db에 저장 
        # title = request.POST.get("title")
        # author = request.POST.get("author")
        # publisher = request.POST.get("publisher")
        # sales = request.POST.get("sales")
        # ip = request.META["REMOTE_ADDR"]
        # book = Book(title=title, author=author, publisher=publisher, sales=sales, ip=ip)
        # book.save()
        # return redirect(book) 
        form = BookModelForm(request.POST)
        print(form)
        print('유효성 검증 결과 :', form.is_valid())
        print(form.cleaned_data)
        if form.is_valid(): # 유효성검사
            book=form.save(commit=False)
            book.ip=request.META.get("REMOTE_ADDR","localhost")
            book.save()
            return redirect(book)
    elif request.method == "GET":
        form = BookModelForm()
    return render(request, "book/book_form.html", {'form':form})
    
book_new = CreateView.as_view(model=Book, 
                            fields=['title', 'author', 'publisher', 'sales']) # book.ip에는  null로 insert

class BookCreateView(CreateView):
    model = Book
    fields=['title', 'author', 'publisher', 'sales']
    def form_valid(self, form): # CreateView내의 함수를 오버라이드(재정의)
        book = form.save(commit=False)
        book.ip = self.request.META.get("REMOTE_ADDR","localhost")
        book.save()
        return redirect(book)
book_new = BookCreateView.as_view()

def book_edit1(request, pk):
    # GET: 수정 TEMPLATE페이지(book)만 응답
    # POST: 파라미터 받아 유효성 체크
        # 1)success: db에 update -> book:list
        # 2)fail: 오류메세지가 담긴 form객체와 함께 수정 template 페이지로 이동
    book = get_object_or_404(Book, id=pk)
    if request.method == "POST":
        form = BookModelForm(request.POST, instance=book) # insert
        if form.is_valid():
            ## 수정 시에도 ip수정
            # book = form.save(commit=False)
            # book.ip = request.META.get('REMOTE_ADDR', 'localhost')
            # book.save()

            # 수정 시에는 ip수정 안함
            book=form.save()
            return redirect(book)
        
    elif request.method == "GET":
        form = BookModelForm(instance=book)
    return render(request, "book/book_form.html",{"form":form})

book_edit = UpdateView.as_view(model=Book,
                            fields=['title', 'author', 'publisher', 'sales'])

def book_delete1(request, pk):
    # GET : 삭제할지 물어보는 template으로 응답
    # book = get_object_or_404(Book, id=pk)
    # book.delete()
    # return redirect(book)

    # POST : db에 delete
    book = get_object_or_404(Book, id=pk)
    if request.method == "POST":
        book.delete()
        return redirect(book)
    elif request.method == "GET":
        return render(request, "book/book_confirm_delete.html", {"object":book})

book_delete = DeleteView.as_view(model=Book,
                                success_url = reverse_lazy("book:list"), # delete후에 반환하여 실행
                                # template_name="",
                                )