from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from myapp.models import Quiz, Question, Choice

QTYPE_CHOICES = Question._meta.get_field("qtype").choices

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ["title", "description", "time_limit_minutes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'title' in self.fields:
            self.fields['title'].widget.attrs.update({
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter quiz title',
            })
        if 'description' in self.fields:
            self.fields['description'].widget.attrs.update({
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Short description (optional)',
            })

class QuestionForm(forms.ModelForm):
    qtype = forms.ChoiceField(choices=QTYPE_CHOICES, initial="short", required=True)

    class Meta:
        model = Question
        fields = ["text", "qtype", "order"]
        widgets = {
            "order": forms.HiddenInput(),
        }

class BaseChoiceInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        choices = []
        correct_count = 0
        for form in self.forms:
            if form.cleaned_data.get("DELETE", False):
                continue
            text = form.cleaned_data.get("text")
            is_correct = form.cleaned_data.get("is_correct", False)
            if not text:
                continue
            choices.append(text)
            if is_correct:
                correct_count += 1

        qtype = None
        if hasattr(self.instance, "qtype") and getattr(self.instance, "qtype", None):
            qtype = self.instance.qtype
        else:
            qtype = getattr(self, "_parent_qtype", None)

        if qtype == "mcq":
            if len(choices) < 2:
                raise forms.ValidationError("at least 2 choices")
            if correct_count != 1:
                raise forms.ValidationError("exactly one choice must be marked correct")


def make_choice_formset(extra=0, can_delete=True):
    return inlineformset_factory(
        Question,
        Choice,
        fields=("text", "is_correct"),
        extra=extra,
        can_delete=can_delete,
        formset=BaseChoiceInlineFormSet
    )
