from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import StyledAuthenticationForm, StyledUserCreationForm

User = get_user_model()

def login_view(request):
    next_url = request.GET.get("next") or request.POST.get("next")
    if request.method == "POST":
        form = StyledAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(next_url or "home")
    else:
        form = StyledAuthenticationForm(request)
    return render(request, "auth/login.html", {"form": form, "next": next_url})


def register_view(request):
    if request.method == "POST":
        form = StyledUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful. Please log in.")
            return redirect("login")
    else:
        form = StyledUserCreationForm()
    return render(request, "auth/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")
