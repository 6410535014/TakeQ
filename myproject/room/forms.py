from django import forms
from .models import Room

class RoomCreateForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class JoinRoomByCodeForm(forms.Form):
	code = forms.CharField(max_length=12)

class InviteForm(forms.Form):
    username = forms.CharField(max_length=150, help_text='Username or email of user to invite')
    role = forms.ChoiceField(choices=[('student','สมาชิก'),('admin','ผู้ดูแลห้อง')])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "class": "form-control",
        })
        self.fields["role"].widget.attrs.update({
            "class": "form-select"
        })
