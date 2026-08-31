from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

from .models import User



class RegisterUserForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        field = ['password',' username','first_name','last_name','email']

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nazwa użytkownika'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Hasło'})
    )