from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from myapp.models import Quiz, Question, Choice

QTYPE_CHOICES = Question._meta.get_field("qtype").choices

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ["title", "description", "time_limit_minutes"]

class QuestionForm(forms.ModelForm):
    # override to remove empty choice and set default
    qtype = forms.ChoiceField(choices=QTYPE_CHOICES, initial="short", required=True)

    class Meta:
        model = Question
        # keep order in model but we won't render it on edit page
        fields = ["text", "qtype", "order"]
        widgets = {
            "order": forms.HiddenInput(),  # hide by default; we'll set when creating
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
            if text in (None, ""):
                continue
            choices.append(text)
            if is_correct:
                correct_count += 1

        qtype = None
        if hasattr(self.instance, "qtype") and self.instance.qtype:
            qtype = self.instance.qtype
        else:
            qtype = getattr(self, "_parent_qtype", None)

        if qtype == "mcq":
            if len(choices) < 2:
                raise forms.ValidationError("Multiple-choice question must have at least 2 choices.")
            if correct_count < 1:
                raise forms.ValidationError("At least one choice must be marked correct for multiple-choice questions.")

def make_choice_formset(extra=0, can_delete=True):
    return inlineformset_factory(
        Question,
        Choice,
        fields=("text", "is_correct"),
        extra=extra,
        can_delete=can_delete,
        formset=BaseChoiceInlineFormSet
    )
