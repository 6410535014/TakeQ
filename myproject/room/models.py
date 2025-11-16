from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.apps import apps

User = get_user_model()

class Room(models.Model):
    code = models.CharField(max_length=12, unique=True, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_rooms')
    created_at = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            import random, string
            self.code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

class RoomMembership(models.Model):
	ROLE_OWNER = 'owner'
	ROLE_ADMIN = 'admin'
	ROLE_STUDENT = 'student'
	ROLE_CHOICES = [
		(ROLE_OWNER, 'Owner'),
		(ROLE_ADMIN, 'Admin'),
		(ROLE_STUDENT, 'Student'),
	]

	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_memberships')
	role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)
	joined_at = models.DateTimeField(default=timezone.now)

	class Meta:
		unique_together = ('room', 'user')

	def __str__(self):
		return f"Quiz {self.quiz_id} assigned to {self.room}"

class RoomInvitation(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_ACCEPTED = 'accepted'
	STATUS_DECLINED = 'declined'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_ACCEPTED, 'Accepted'),
		(STATUS_DECLINED, 'Declined'),
	]

	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='invitations')
	invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_invitations')
	invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_room_invitations')
	role = models.CharField(max_length=10, choices=[('admin','Admin'),('student','Student')], default='student')
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
	created_at = models.DateTimeField(default=timezone.now)
	responded_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		unique_together = ('room', 'invited_user')

	def accept(self):
		if self.status != self.STATUS_PENDING:
			return
		RoomMembership.objects.create(room=self.room, user=self.invited_user, role=self.role)
		self.status = self.STATUS_ACCEPTED
		self.responded_at = timezone.now()
		self.save()

	def decline(self):
		if self.status != self.STATUS_PENDING:
			return
		self.status = self.STATUS_DECLINED
		self.responded_at = timezone.now()
		self.save()

	def __str__(self):
		return f"Quiz {self.quiz_id} assigned to {self.room}"

class RoomQuizAssignment(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='assignments')
    quiz = models.ForeignKey('myapp.Quiz', on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ('room', 'quiz')

    def __str__(self):
        quiz_title = getattr(self.quiz, 'title', f'#{getattr(self.quiz, "pk", "unknown")}')
        return f"Quiz {quiz_title} assigned to {self.room}"

