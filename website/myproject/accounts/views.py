from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegisterUserForm, UserLoginForm


def login_view(request):

    if request.method == "POST":
        form = UserLoginForm(request.POST)

        if form.is_valid():

            user = form.get_user()
            login(request,user)

            return redirect('/')

    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form' : form})

def register_view(request):

    if request.method == "POST":

        form = RegisterUserForm(request.POST)

        if form.is_valid():
            form.save()

            return redirect('/')


    else:
        form = RegisterUserForm()

    return render(request,'accounts/register.html', {'form' : form})




