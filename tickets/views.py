from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from .forms import RegisterForm


@login_required()
@ensure_csrf_cookie
def dashboard(request):
    return render(request, "dashboard.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})
