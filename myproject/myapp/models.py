from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,   
        blank=True,  
    )
    is_teacher = models.BooleanField(default=False)

class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_quizzes",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,      
        blank=True,
    )
    text = models.TextField()
    qtype = models.CharField(
        max_length=20,
        choices=(
            ("mcq", "ตัวเลือก"),
            ("short", "คำตอบสั้น ๆ"),
        ),
    )
    order = models.PositiveIntegerField(default=0)
    correct_text = models.TextField(blank=True, default="", help_text="...")


class Choice(models.Model):
   
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
        null=True,
        blank=True,
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)


class Attempt(models.Model):
   
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
        null=True,
        blank=True,
    )
    taker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)

    room = models.ForeignKey(
        'room.Room',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    room_membership = models.ForeignKey(
        'room.RoomMembership',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    room_code = models.CharField(max_length=20, null=True, blank=True)


class Answer(models.Model):
    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name="answers",
        null=True,
        blank=True,
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    text = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True, help_text="...")
