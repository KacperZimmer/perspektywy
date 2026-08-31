from django.shortcuts import redirect, render

from .forms import RegisterUserForm


def register_view(request):

    if request.method == "POST":

        form = RegisterUserForm(request.POST)

        if form.is_valid():
            form.save()

            return redirect('')


    else:
        form = RegisterUserForm()

    return render(request,'accounts/register.html', {'form' : form})




