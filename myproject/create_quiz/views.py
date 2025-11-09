from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from myapp.models import Quiz, Question, Choice
from .forms import QuizForm, QuestionForm, make_choice_formset
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required


@method_decorator(login_required, name="dispatch")
class QuizListView(ListView):
	model = Quiz
	template_name = "create_quiz/quiz_list.html"
	context_object_name = "quizzes"

	def get_queryset(self):
		return Quiz.objects.filter(creator=self.request.user).order_by("-created_at")

@method_decorator(login_required, name="dispatch")
class QuizCreateView(CreateView):
	model = Quiz
	form_class = QuizForm
	template_name = "create_quiz/quiz_form.html"

	def form_valid(self, form):
		obj = form.save(commit=False)
		obj.creator = self.request.user
		obj.is_published = False
		obj.save()
		return redirect("create_quiz:quiz_detail", pk=obj.pk)

@method_decorator(login_required, name="dispatch")
class QuizUpdateView(UpdateView):
    model = Quiz
    form_class = QuizForm
    template_name = "create_quiz/quiz_form.html"

    def get_queryset(self):
        return Quiz.objects.filter(creator=self.request.user)

    def get_success_url(self):
        return reverse("create_quiz:quiz_detail", args=[self.object.pk])

@method_decorator(login_required, name="dispatch")
class QuizDetailView(DetailView):
	model = Quiz
	template_name = "create_quiz/quiz_detail.html"
	context_object_name = "quiz"

	def get_queryset(self):
		return Quiz.objects.filter(creator=self.request.user)
     
class QuizDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Quiz
    template_name = "create_quiz/quiz_confirm_delete.html"
    success_url = reverse_lazy("create_quiz:quiz_list")

    def test_func(self):
        obj = self.get_object()
        return obj.creator == self.request.user


@login_required
def add_question(request, quiz_id):
    """
    Robust add-question view:
    - make a mutable copy of POST and fill defaults (order, qtype) so QuestionForm validates
    - always use prefix "choice_set" for Choice formset binding
    - when formset invalid, attach formset.non_form_errors into qform non-field errors for reliable display
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id, creator=request.user)
    ChoiceFormSetClass = make_choice_formset(extra=1, can_delete=True)
    prefix = "choice_set"

    if request.method == "POST":
        post = request.POST.copy()
        if not post.get("qtype"):
            post["qtype"] = "short"
        if not post.get("order"):
            post["order"] = str(quiz.questions.count() + 1)

        qform = QuestionForm(post)
        qform_is_valid = qform.is_valid()
        posted_qtype = post.get("qtype")

        question_instance = None
        if qform_is_valid:
            question_instance = qform.save(commit=False)
            question_instance.quiz = quiz
            if not question_instance.order:
                question_instance.order = quiz.questions.count() + 1
            question_instance.save()

        if posted_qtype == "mcq":
            if question_instance:
                formset = ChoiceFormSetClass(post, instance=question_instance, prefix=prefix)
            else:
                formset = ChoiceFormSetClass(post, prefix=prefix)
        else:
            formset = None

        if qform_is_valid:
            if posted_qtype == "mcq":
                if formset.is_valid():
                    formset.save()
                    return redirect("create_quiz:quiz_detail", pk=quiz.pk)
                else:
                    for err in formset.non_form_errors():
                        qform.add_error(None, err)
                    return render(request, "create_quiz/question_form.html", {
                        "form": qform,
                        "quiz": quiz,
                        "formset": formset,
                        "is_new": True,
                    })
            else:
                return redirect("create_quiz:quiz_detail", pk=quiz.pk)
        else:
            if posted_qtype == "mcq":
                formset = ChoiceFormSetClass(post, prefix=prefix)
                for err in formset.non_form_errors():
                    qform.add_error(None, err)
            else:
                formset = None

            return render(request, "create_quiz/question_form.html", {
                "form": qform,
                "quiz": quiz,
                "formset": formset,
                "is_new": True,
            })

    initial_order = quiz.questions.count() + 1
    qform = QuestionForm(initial={"order": initial_order, "qtype": "short"})
    formset = ChoiceFormSetClass(prefix=prefix)
    return render(request, "create_quiz/question_form.html", {
        "form": qform,
        "quiz": quiz,
        "formset": formset,
        "is_new": True,
    })


@login_required
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk, quiz__creator=request.user)
    ChoiceFormSetClass = make_choice_formset(extra=0, can_delete=True)
    prefix = "choice_set"

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        qtype = request.POST.get("qtype") or question.qtype

        if qtype == "mcq":
            formset = ChoiceFormSetClass(request.POST, instance=question, prefix=prefix)
            formset._parent_qtype = "mcq"
        else:
            formset = None

        if form.is_valid() and (formset is None or formset.is_valid()):
            form.save()
            if formset:
                formset.save()
            return redirect("create_quiz:quiz_detail", pk=question.quiz.pk)
        else:
            if qtype == "mcq" and not formset:
                formset = ChoiceFormSetClass(request.POST, prefix=prefix)
            return render(request, "create_quiz/question_form.html", {
                "form": form,
                "formset": formset,
                "question": question,
                "is_new": False,
            })

    form = QuestionForm(instance=question)
    if question.qtype == "mcq":
        formset = ChoiceFormSetClass(instance=question, prefix=prefix)
    else:
        formset = None

    return render(request, "create_quiz/question_form.html", {
        "form": form,
        "formset": formset,
        "question": question,
        "is_new": False,
    })



@login_required
def toggle_publish(request, pk):
	quiz = get_object_or_404(Quiz, pk=pk, creator=request.user)
	quiz.is_published = not quiz.is_published
	quiz.save()
	return redirect("create_quiz:quiz_detail", pk=pk)


@login_required
@require_POST
def reorder_questions(request, quiz_id):
    """
    Expect JSON body: {"order": [question_id_3, question_id_1, question_id_2, ...]}
    Only quiz.creator can reorder.
    """
    import json
    quiz = get_object_or_404(Quiz, pk=quiz_id, creator=request.user)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        new_order = payload.get("order", [])
        if not isinstance(new_order, list):
            return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    q_ids = list(quiz.questions.values_list("id", flat=True))
    if set(new_order) - set(q_ids):
        return JsonResponse({"ok": False, "error": "invalid question ids"}, status=400)

    from django.db import transaction
    with transaction.atomic():
        for idx, qid in enumerate(new_order, start=1):
            Question.objects.filter(pk=qid, quiz=quiz).update(order=idx)

    return JsonResponse({"ok": True})
