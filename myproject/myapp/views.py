from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request,"index.html")

def about(request):
    return render(request,"about.html")

def home(request):
    if request.user.is_authenticated:
        return render(request, "dashboard.html", {})
    return render(request, "index.html", {})
