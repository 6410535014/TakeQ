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
		# creators see their quizzes first; teachers can extend permission later
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
        # redirect to quiz detail after successful edit
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
    # redirect to quiz list after successful delete
    success_url = reverse_lazy("create_quiz:quiz_list")

    def test_func(self):
        # only allow creator to delete
        obj = self.get_object()
        return obj.creator == self.request.user


@login_required
def add_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, creator=request.user)

    if request.method == "POST":
        qform = QuestionForm(request.POST)
        if qform.is_valid():
            # create question record first so formset can bind to instance
            q = qform.save(commit=False)
            q.quiz = quiz
            # set order to end if not provided or zero
            if not q.order:
                q.order = quiz.questions.count() + 1
            q.save()

            # only process choices when MCQ
            if q.qtype == "mcq":
                ChoiceFormSet = make_choice_formset(extra=0, can_delete=True)
                formset = ChoiceFormSet(request.POST, instance=q)
                # formset has access to instance so validation can check existing values
                if formset.is_valid():
                    formset.save()
                    return redirect("create_quiz:quiz_detail", pk=quiz.pk)
                else:
                    # formset invalid -> render form with errors (question already saved; consider rollback)
                    # optionally delete q to keep DB clean when invalid choices
                    q.delete()
            else:
                # short answer: no choice formset to process
                return redirect("create_quiz:quiz_detail", pk=quiz.pk)
        # fallthrough: qform invalid OR formset invalid -> render form with errors
        # Note: if q was saved and then deleted above on formset invalid, we need to re-create qform for render
        return render(request, "create_quiz/question_form.html", {
            "form": qform,
            "quiz": quiz,
            "formset": locals().get("formset", None),
            "is_new": True,
        })

    # GET
    initial_order = quiz.questions.count() + 1
    qform = QuestionForm(initial={"order": initial_order, "qtype": "short"})
    ChoiceFormSet = make_choice_formset(extra=1, can_delete=True)
    formset = ChoiceFormSet()
    return render(request, "create_quiz/question_form.html", {
        "form": qform,
        "quiz": quiz,
        "formset": formset,
        "is_new": True,
    })


@login_required
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk, quiz__creator=request.user)

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        qtype = request.POST.get("qtype") or question.qtype
        if qtype == "mcq":
            ChoiceFormSet = make_choice_formset(extra=0, can_delete=True)
            formset = ChoiceFormSet(request.POST, instance=question)
            formset._parent_qtype = "mcq"
        else:
            formset = None

        if form.is_valid() and (formset is None or formset.is_valid()):
            form.save()
            if formset:
                formset.save()
            return redirect("create_quiz:quiz_detail", pk=question.quiz.pk)
    else:
        form = QuestionForm(instance=question)
        # only prepare formset when editing MCQ
        if question.qtype == "mcq":
            ChoiceFormSet = make_choice_formset(extra=0, can_delete=True)
            formset = ChoiceFormSet(instance=question)
        else:
            # render no choice forms for short-answer
            ChoiceFormSet = make_choice_formset(extra=0, can_delete=True)
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


# --- เพิ่ม endpoint สำหรับ reorder ---
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

    # validate that provided ids belong to this quiz
    q_ids = list(quiz.questions.values_list("id", flat=True))
    if set(new_order) - set(q_ids):
        return JsonResponse({"ok": False, "error": "invalid question ids"}, status=400)

    # update orders in a transaction
    from django.db import transaction
    with transaction.atomic():
        for idx, qid in enumerate(new_order, start=1):
            Question.objects.filter(pk=qid, quiz=quiz).update(order=idx)

    return JsonResponse({"ok": True})
