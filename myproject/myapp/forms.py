from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'username',
                'autofocus': 'autofocus',
            })
        if 'password' in self.fields:
            self.fields['password'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'password',
            })

class StyledUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            attrs = {'class': 'form-control'}
            if name == 'username':
                attrs.update({'placeholder': 'username', 'autofocus': 'autofocus'})
            elif name in ('password1', 'password2'):
                attrs.update({'placeholder': 'password'})
            elif name == 'email':
                attrs.update({'placeholder': 'you@example.com'})
            field.widget.attrs.update(attrs)
