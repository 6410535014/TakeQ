from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from myapp.models import Quiz, Question, Choice, Attempt, Answer
from .forms import QuizForm, QuestionForm, make_choice_formset
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.views.decorators.http import require_POST
from room.models import RoomQuizAssignment, RoomMembership, Room
from django.contrib.auth import get_user_model
from django.apps import apps
from django.contrib import messages
from django.views import View
from room.models import Room
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

RoomQuizAssignment = apps.get_model('room', 'RoomQuizAssignment')
RoomMembership     = apps.get_model('room', 'RoomMembership')

def user_is_room_owner_or_admin_for_quiz(user, quiz):
    room_ids = list(RoomQuizAssignment.objects.filter(quiz=quiz).values_list('room_id', flat=True))
    if not room_ids:
        return False

    allowed_roles = [
        getattr(RoomMembership, 'ROLE_OWNER', 'owner'),
        getattr(RoomMembership, 'ROLE_ADMIN',  'admin'),
        'owner', 'admin'
    ]

    return RoomMembership.objects.filter(user=user, room_id__in=room_ids, role__in=allowed_roles).exists()

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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        room_code = self.request.GET.get('room') or self.request.session.get('last_room_for_quiz_new')
        ctx['room_code'] = room_code
        return ctx

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.creator = self.request.user
        obj.is_published = False
        obj.save()

        room_code = (
            self.request.GET.get('room')
            or self.request.POST.get('room')
            or self.request.session.get('last_room_for_quiz_new')
        )

        if room_code:
            self.request.session[f"last_room_for_quiz_{obj.pk}"] = room_code
            if 'last_room_for_quiz_new' in self.request.session:
                try:
                    del self.request.session['last_room_for_quiz_new']
                except KeyError:
                    pass

            detail_url = reverse("create_quiz:quiz_detail", args=[obj.pk])
            return redirect(f"{detail_url}?room={room_code}")

        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect("create_quiz:quiz_detail", pk=obj.pk)

    def form_invalid(self, form):
        room_code = self.request.GET.get('room') or self.request.POST.get('room')
        if room_code:
            self.request.session['last_room_for_quiz_new'] = room_code
        return super().form_invalid(form)


@method_decorator(login_required, name="dispatch")
class QuizUpdateView(UpdateView):
    model = Quiz
    form_class = QuizForm
    template_name = "create_quiz/quiz_form.html"

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        quiz = get_object_or_404(Quiz, pk=pk)
        if not (quiz.creator == self.request.user or user_is_room_owner_or_admin_for_quiz(self.request.user, quiz)):
            raise Http404("No quiz found matching the query")
        return quiz

    def get_success_url(self):
        return reverse("create_quiz:quiz_detail", args=[self.object.pk])
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        room_code = self.request.GET.get('room')
        if room_code:
            _set_last_room_for_quiz_in_session(self.request, self.object.pk, room_code)
        ctx['room_code'] = room_code or self.request.session.get(f"last_room_for_quiz_{self.object.pk}")
        return ctx


@method_decorator(login_required, name="dispatch")
class QuizDetailView(DetailView):
    model = Quiz
    template_name = "create_quiz/quiz_detail.html"
    context_object_name = "quiz"

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        quiz = get_object_or_404(Quiz, pk=pk)
        if not (quiz.creator == self.request.user or user_is_room_owner_or_admin_for_quiz(self.request.user, quiz)):
            raise Http404("No quiz found matching the query")
        return quiz
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        quiz = self.get_object()
        room_code = self.request.GET.get('room') or self.request.session.get(f"last_room_for_quiz_{quiz.pk}")
        ctx['room_code'] = room_code
        ctx['is_room_admin'] = user_is_room_owner_or_admin_for_quiz(self.request.user, quiz)
        return ctx


class QuizDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Quiz
    template_name = "create_quiz/quiz_confirm_delete.html"
    success_url = reverse_lazy("create_quiz:quiz_list")

    def test_func(self):
        obj = self.get_object()
        return obj.creator == self.request.user


@login_required
def add_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

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
    question = get_object_or_404(Question, pk=pk)
    quiz = question.quiz
    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

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
    if request.method != "POST":
        return HttpResponseForbidden()

    quiz = get_object_or_404(Quiz, pk=pk)

    if quiz.creator == request.user:
        allowed = True
    else:
        assignments = RoomQuizAssignment.objects.filter(quiz=quiz).select_related('room')
        allowed = False
        for assign in assignments:
            room = assign.room
            try:
                membership = RoomMembership.objects.get(user=request.user, room=room)
                if membership.role in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
                    allowed = True
                    break
            except RoomMembership.DoesNotExist:
                continue

    if not allowed:
        return HttpResponseForbidden()

    quiz.is_published = not quiz.is_published
    quiz.save()

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect("create_quiz:quiz_detail", pk=pk)


@login_required
@require_POST
def reorder_questions(request, quiz_id):
    import json
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

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

def delete_question(request, pk):
    if request.method != "POST":
        return redirect('create_quiz:quiz_list')

    question = get_object_or_404(Question, pk=pk)
    quiz = question.quiz

    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

    question.delete()
    messages.success(request, "Question deleted.")

    return redirect('create_quiz:quiz_detail', pk=quiz.pk)


@method_decorator(login_required, name='dispatch')
class QuizAttemptsListView(ListView):
    model = Attempt
    template_name = "create_quiz/quiz_attempts.html"
    context_object_name = "attempts"

    def dispatch(self, request, *args, **kwargs):
        self.quiz = get_object_or_404(apps.get_model('myapp', 'Quiz'), pk=kwargs['pk'])
        if not (self.quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, self.quiz)):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        Attempt = apps.get_model('myapp', 'Attempt')
        return Attempt.objects.filter(quiz=self.quiz).select_related('taker').order_by('-started_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['quiz'] = self.quiz
        return ctx
    

@login_required
def attempt_detail(request, attempt_id):
    Attempt = apps.get_model('myapp', 'Attempt')
    Answer = apps.get_model('myapp', 'Answer')
    Choice = apps.get_model('myapp', 'Choice')
    attempt = get_object_or_404(Attempt, pk=attempt_id)
    quiz = attempt.quiz

    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

    answers = attempt.answers.select_related('question', 'selected_choice').all().order_by('question__order', 'question__id')

    answer_rows = []
    for a in answers:
        row = {
            'question': a.question,
            'selected_choice': a.selected_choice,
            'text': a.text,
            'is_correct': a.is_correct,
            'answer_id': a.pk,
        }
        answer_rows.append(row)

    return render(request, 'create_quiz/attempt_detail.html', {
        'quiz': quiz,
        'attempt': attempt,
        'answer_rows': answer_rows,
    })

def _set_last_room_for_quiz_in_session(request, quiz_pk, room_code):
    if not room_code:
        return
    key = f"last_room_for_quiz_{quiz_pk}"
    request.session[key] = room_code

@require_POST
def quiz_delete(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)

    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

    posted_room = (request.POST.get('room') or "").strip()
    session_key = f"last_room_for_quiz_{quiz.pk}"
    session_room = request.session.get(session_key)

    room_code_candidate = posted_room or session_room

    if room_code_candidate and Room.objects.filter(code=room_code_candidate).exists():
        redirect_to = reverse('room:detail', args=[room_code_candidate])
    else:
        redirect_to = reverse('create_quiz:quiz_list')

    quiz.delete()

    try:
        if session_key in request.session:
            del request.session[session_key]
    except Exception:
        pass

    messages.success(request, "Quiz deleted.")
    return redirect(redirect_to)

@require_POST
def mark_answer(request, answer_id):
    ans = get_object_or_404(Answer, pk=answer_id)
    attempt = ans.attempt
    quiz = attempt.quiz

    if not (quiz.creator == request.user or user_is_room_owner_or_admin_for_quiz(request.user, quiz)):
        return HttpResponseForbidden()

    mark = request.POST.get("mark")
    if mark == "correct":
        ans.is_correct = True
    else:
        ans.is_correct = False
    ans.save()

    questions = quiz.questions.all()
    gradable_qs = questions.filter(qtype__in=["mcq", "short"])
    total_gradable = gradable_qs.count()

    correct_count = 0
    for q in gradable_qs:
        if q.qtype == "mcq":
            a = attempt.answers.filter(question=q).first()
            if a and a.selected_choice and getattr(a.selected_choice, "is_correct", False):
                correct_count += 1
        else:
            a = attempt.answers.filter(question=q).first()
            if a and a.is_correct is True:
                correct_count += 1

    if total_gradable > 0:
        attempt.score = (correct_count / total_gradable) * 100.0
    else:
        attempt.score = None

    attempt.save()

    messages.success(request, "Answer marked.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)
