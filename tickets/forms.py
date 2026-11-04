from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        self.fields["username"].widget.attrs.update({
            "placeholder": "Придумайте имя пользователя",
            "autofocus": "autofocus",
        })
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Введите пароль",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Повторите пароль",
            "autocomplete": "new-password",
        })
