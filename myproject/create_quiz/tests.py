# create_quiz/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

from myapp.models import Quiz, Question, Choice

User = get_user_model()

CHOICE_PREFIX = "choice_set"


class CreateQuizFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(username="teacher", password="teachpw")
        self.other = User.objects.create_user(username="other", password="otherpw")

        self.quiz = Quiz.objects.create(
            title="Initial Quiz",
            description="desc",
            creator=self.teacher,
            is_published=False,
            time_limit_minutes=None,
            created_at=timezone.now()
        )


    def test_create_quiz_view_and_redirect(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:quiz_create")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        r2 = self.client.post(url, {"title": "New Quiz", "description": "x", "time_limit_minutes": ""})
        self.assertEqual(r2.status_code, 302)
        q = Quiz.objects.filter(title="New Quiz").first()
        self.assertIsNotNone(q)
        self.assertEqual(q.creator, self.teacher)

    def test_add_mcq_question_happy(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:add_question", args=[self.quiz.pk])

        data = {
            "text": "What is 2+2?",
            "qtype": "mcq",
            "order": "",
            f"{CHOICE_PREFIX}-TOTAL_FORMS": "2",
            f"{CHOICE_PREFIX}-INITIAL_FORMS": "0",
            f"{CHOICE_PREFIX}-MIN_NUM_FORMS": "0",
            f"{CHOICE_PREFIX}-MAX_NUM_FORMS": "1000",
            f"{CHOICE_PREFIX}-0-text": "3",
            f"{CHOICE_PREFIX}-0-is_correct": "",  
            f"{CHOICE_PREFIX}-1-text": "4",
            f"{CHOICE_PREFIX}-1-is_correct": "on",  
        }

        r = self.client.post(url, data)
        self.assertIn(r.status_code, (302, 303))
        qn = Question.objects.filter(quiz=self.quiz, text="What is 2+2?").first()
        self.assertIsNotNone(qn)
        choices = list(Choice.objects.filter(question=qn).order_by("id"))
        self.assertEqual(len(choices), 2)
        self.assertTrue(any(c.is_correct for c in choices))
        self.assertEqual(sum(1 for c in choices if c.is_correct), 1)

    def test_add_short_question_happy(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:add_question", args=[self.quiz.pk])

        data = {
            "text": "Explain something",
            "qtype": "short",
            "order": "",
            f"{CHOICE_PREFIX}-TOTAL_FORMS": "0",
            f"{CHOICE_PREFIX}-INITIAL_FORMS": "0",
            f"{CHOICE_PREFIX}-MIN_NUM_FORMS": "0",
            f"{CHOICE_PREFIX}-MAX_NUM_FORMS": "1000",
        }

        r = self.client.post(url, data)
        self.assertIn(r.status_code, (302, 303))
        qn = Question.objects.filter(quiz=self.quiz, text="Explain something").first()
        self.assertIsNotNone(qn)
        self.assertEqual(Choice.objects.filter(question=qn).count(), 0)

    def test_delete_quiz_by_creator(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:quiz_delete", args=[self.quiz.pk])
        r = self.client.post(url)
        self.assertIn(r.status_code, (302, 303))
        self.assertFalse(Quiz.objects.filter(pk=self.quiz.pk).exists())

    def test_reorder_questions_happy(self):
        q1 = Question.objects.create(quiz=self.quiz, text="A", qtype="short", order=1)
        q2 = Question.objects.create(quiz=self.quiz, text="B", qtype="short", order=2)
        q3 = Question.objects.create(quiz=self.quiz, text="C", qtype="short", order=3)

        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:reorder_questions", args=[self.quiz.pk])
        new_order = [q3.pk, q1.pk, q2.pk]
        r = self.client.post(url, json.dumps({"order": new_order}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        orders = list(Question.objects.filter(quiz=self.quiz).order_by("order").values_list("text", flat=True))
        self.assertEqual(orders, ["C", "A", "B"])


    def test_create_requires_login(self):
        url = reverse("create_quiz:quiz_create")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_edit_not_creator_forbidden_or_404(self):
        qn = Question.objects.create(quiz=self.quiz, text="X", qtype="short", order=1)
        assert self.client.login(username="other", password="otherpw")
        url = reverse("create_quiz:quiz_edit", args=[self.quiz.pk])
        r = self.client.get(url)
        self.assertIn(r.status_code, (403, 404))

    def test_add_mcq_invalid_too_few_choices(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:add_question", args=[self.quiz.pk])

        data = {
            "text": "Bad MCQ",
            "qtype": "mcq",
            f"{CHOICE_PREFIX}-TOTAL_FORMS": "1",
            f"{CHOICE_PREFIX}-INITIAL_FORMS": "0",
            f"{CHOICE_PREFIX}-MIN_NUM_FORMS": "0",
            f"{CHOICE_PREFIX}-MAX_NUM_FORMS": "1000",
            f"{CHOICE_PREFIX}-0-text": "only one",
            f"{CHOICE_PREFIX}-0-is_correct": "on",
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "at least 2 choices", status_code=200)

    def test_add_mcq_invalid_not_exactly_one_correct(self):
        assert self.client.login(username="teacher", password="teachpw")
        url = reverse("create_quiz:add_question", args=[self.quiz.pk])

        data = {
            "text": "Bad MCQ 2",
            "qtype": "mcq",
            f"{CHOICE_PREFIX}-TOTAL_FORMS": "2",
            f"{CHOICE_PREFIX}-INITIAL_FORMS": "0",
            f"{CHOICE_PREFIX}-MIN_NUM_FORMS": "0",
            f"{CHOICE_PREFIX}-MAX_NUM_FORMS": "1000",
            f"{CHOICE_PREFIX}-0-text": "opt1",
            f"{CHOICE_PREFIX}-0-is_correct": "on",
            f"{CHOICE_PREFIX}-1-text": "opt2",
        }
        data_zero = data.copy()
        data_zero[f"{CHOICE_PREFIX}-0-is_correct"] = ""  
        data_zero[f"{CHOICE_PREFIX}-1-is_correct"] = ""  
        r0 = self.client.post(url, data_zero)
        self.assertEqual(r0.status_code, 200)
        self.assertContains(r0, "exactly one choice must be marked correct", status_code=200)

        data_many = data.copy()
        data_many[f"{CHOICE_PREFIX}-1-is_correct"] = "on"
        r1 = self.client.post(url, data_many)
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, "exactly one choice must be marked correct", status_code=200)

    def test_delete_permission_forbidden_for_non_creator(self):
        assert self.client.login(username="other", password="otherpw")
        url = reverse("create_quiz:quiz_delete", args=[self.quiz.pk])
        r = self.client.post(url)
        self.assertIn(r.status_code, (403, 404))

    def test_reorder_forbidden_for_non_creator(self):
        q1 = Question.objects.create(quiz=self.quiz, text="A", qtype="short", order=1)
        assert self.client.login(username="other", password="otherpw")
        url = reverse("create_quiz:reorder_questions", args=[self.quiz.pk])
        r = self.client.post(url, json.dumps({"order": [q1.pk]}), content_type="application/json")
        self.assertIn(r.status_code, (403, 404))
