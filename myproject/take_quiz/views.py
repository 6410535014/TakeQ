from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from myapp.models import Quiz, Choice, Attempt, Answer
from django.contrib import messages
from django.db import transaction, IntegrityError

@method_decorator(login_required, name='dispatch')
class QuizListView(ListView):
    model = Quiz
    template_name = "take_quiz/quiz_list.html"
    context_object_name = "quizzes"

    def get_queryset(self):
        return Quiz.objects.filter(is_published=True).order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            attempted_quiz_ids = list(
                Attempt.objects.filter(taker=self.request.user).values_list('quiz_id', flat=True)
            )
        else:
            attempted_quiz_ids = []
        ctx['attempted_quiz_ids'] = attempted_quiz_ids
        return ctx


@login_required
def start_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)

    room_code = request.GET.get("room") or request.POST.get("room")
    
    existing = Attempt.objects.filter(quiz=quiz, taker=request.user).first()
    if existing:
        return redirect("take_quiz:attempt_result", attempt_id=existing.id)

    attempt = Attempt.objects.create(
        quiz=quiz,
        taker=request.user,
        started_at=timezone.now(),
        room_code=room_code
    )

    return redirect("take_quiz:take_quiz", quiz_id=quiz.id, attempt_id=attempt.id)


@login_required
def take_quiz(request, quiz_id, attempt_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    attempt = get_object_or_404(Attempt, pk=attempt_id, quiz=quiz, taker=request.user)

    if attempt.finished_at:
        return redirect("take_quiz:attempt_result", attempt_id=attempt.id)

    questions = quiz.questions.all().order_by("order", "id").prefetch_related("choices")

    return render(request, "take_quiz/take_quiz.html", {
        "quiz": quiz,
        "attempt": attempt,
        "questions": questions,
    })


@login_required
@transaction.atomic
def submit_quiz(request, attempt_id):
    if request.method != "POST":
        return redirect("home")

    attempt = get_object_or_404(Attempt, pk=attempt_id, taker=request.user)
    quiz = attempt.quiz

    if attempt.finished_at:
        return redirect("take_quiz:attempt_result", attempt_id=attempt.id)

    questions = quiz.questions.all().order_by("order", "id").prefetch_related("choices")

    correct_count = 0
    total_questions = questions.count()

    attempt.answers.all().delete()

    for q in questions:
        field_name = f"question_{q.id}"
        selected_choice_id = request.POST.get(field_name)
        if q.qtype == "mcq":
            selected_choice = None
            if selected_choice_id:
                try:
                    selected_choice = q.choices.get(pk=int(selected_choice_id))
                except (Choice.DoesNotExist, ValueError):
                    selected_choice = None

            Answer.objects.create(
                attempt=attempt,
                question=q,
                selected_choice=selected_choice,
                text=""
            )
            if selected_choice and selected_choice.is_correct:
                correct_count += 1
        else:
            text_ans = request.POST.get(field_name, "").strip()
            Answer.objects.create(
                attempt=attempt,
                question=q,
                selected_choice=None,
                text=text_ans
            )

    mcq_questions = questions.filter(qtype="mcq").count()
    if mcq_questions > 0:
        score = (correct_count / mcq_questions) * 100.0
    else:
        score = None

    attempt.finished_at = timezone.now()
    attempt.score = score
    attempt.save()

    return redirect("take_quiz:attempt_result", attempt_id=attempt.id)


@login_required
def attempt_result(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, taker=request.user)
    answers = attempt.answers.select_related("question", "selected_choice").all()
    return render(request, "take_quiz/result.html", {
        "attempt": attempt,
        "answers": answers,
    })
