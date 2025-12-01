from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from myapp.models import Quiz
from room.models import Room, RoomMembership, RoomInvitation, RoomQuizAssignment

User = get_user_model()

class RoomAppBehaviorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pw')
        self.admin = User.objects.create_user(username='admin', password='pw')
        self.student = User.objects.create_user(username='student', password='pw')
        self.other = User.objects.create_user(username='other', password='pw')

        self.room = Room.objects.create(name='Test Room', description='desc', owner=self.owner)

        RoomMembership.objects.create(room=self.room, user=self.owner, role=RoomMembership.ROLE_OWNER)
        RoomMembership.objects.create(room=self.room, user=self.admin, role=RoomMembership.ROLE_ADMIN)
        RoomMembership.objects.create(room=self.room, user=self.student, role=RoomMembership.ROLE_STUDENT)

        self.quiz = Quiz.objects.create(title='Quiz A', description='qdesc', creator=self.other, is_published=False)
        RoomQuizAssignment.objects.create(room=self.room, quiz=self.quiz, assigned_by=self.owner)

    def test_owner_can_delete_room(self):
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('room:delete', args=[self.room.code]))
        self.assertIn(resp.status_code, (302, 303))
        self.assertFalse(Room.objects.filter(pk=self.room.pk).exists())

    def test_non_owner_cannot_delete_room(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('room:delete', args=[self.room.code]))
        self.assertIn(resp.status_code, (403, 302))  # 403 expected; if redirect to login it may be 302
        self.assertTrue(Room.objects.filter(pk=self.room.pk).exists())

    def test_owner_and_admin_can_assign_quiz(self):
        q = Quiz.objects.create(title='Quiz B', creator=self.other)
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('room:assign_quiz', args=[self.room.code]), {'quiz_id': q.pk})
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(RoomQuizAssignment.objects.filter(room=self.room, quiz=q).exists())
        RoomQuizAssignment.objects.filter(room=self.room, quiz=q).delete()

        self.client.force_login(self.admin)
        resp = self.client.post(reverse('room:assign_quiz', args=[self.room.code]), {'quiz_id': q.pk})
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(RoomQuizAssignment.objects.filter(room=self.room, quiz=q).exists())

    def test_student_cannot_assign_quiz(self):
        q = Quiz.objects.create(title='Quiz C', creator=self.other)
        self.client.force_login(self.student)
        resp = self.client.post(reverse('room:assign_quiz', args=[self.room.code]), {'quiz_id': q.pk})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(RoomQuizAssignment.objects.filter(room=self.room, quiz=q).exists())

    def test_owner_admin_can_toggle_assigned_quiz_even_if_not_creator(self):
        self.assertFalse(Quiz.objects.get(pk=self.quiz.pk).is_published)

        self.client.force_login(self.owner)
        resp = self.client.post(reverse('create_quiz:toggle_publish', args=[self.quiz.pk]), follow=True)
        self.assertIn(resp.status_code, (200, 302))
        self.quiz.refresh_from_db()
        self.assertTrue(self.quiz.is_published)

        self.client.force_login(self.admin)
        resp = self.client.post(reverse('create_quiz:toggle_publish', args=[self.quiz.pk]), follow=True)
        self.assertIn(resp.status_code, (200, 302))
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_published)
  
    def test_non_member_cannot_toggle_publish(self):
        rand = User.objects.create_user(username='rand', password='pw')
        self.client.force_login(rand)
        resp = self.client.post(reverse('create_quiz:toggle_publish', args=[self.quiz.pk]))
        self.assertEqual(resp.status_code, 403)
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_published)

    def test_owner_can_invite_as_admin_or_member(self):
        self.client.force_login(self.owner)
        target = User.objects.create_user(username='invitee1', password='pw', email='i1@example.com')
        resp = self.client.post(reverse('room:invite', args=[self.room.code]), {'username': target.username, 'role': 'admin'})
        self.assertIn(resp.status_code, (302, 303))
        inv = RoomInvitation.objects.filter(room=self.room, invited_user=target).first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.role, 'admin')

        target2 = User.objects.create_user(username='invitee2', password='pw', email='i2@example.com')
        resp = self.client.post(reverse('room:invite', args=[self.room.code]), {'username': target2.username, 'role': 'student'})
        self.assertIn(resp.status_code, (302, 303))
        inv2 = RoomInvitation.objects.filter(room=self.room, invited_user=target2).first()
        self.assertIsNotNone(inv2)
        self.assertEqual(inv2.role, 'student')

    def test_admin_can_invite_member_only_and_not_admin(self):
        self.client.force_login(self.admin)
        target = User.objects.create_user(username='invitee3', password='pw')
        resp = self.client.post(reverse('room:invite', args=[self.room.code]), {'username': target.username, 'role': 'admin'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(RoomInvitation.objects.filter(room=self.room, invited_user=target).exists())

        resp = self.client.post(reverse('room:invite', args=[self.room.code]), {'username': target.username, 'role': 'student'})
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(RoomInvitation.objects.filter(room=self.room, invited_user=target).exists())

    def test_student_cannot_invite(self):
        self.client.force_login(self.student)
        target = User.objects.create_user(username='invitee4', password='pw')
        resp = self.client.post(reverse('room:invite', args=[self.room.code]), {'username': target.username, 'role': 'student'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(RoomInvitation.objects.filter(room=self.room, invited_user=target).exists())

    def test_invitations_list_shows_pending_invites_for_target_user(self):
        target = User.objects.create_user(username='invitee5', password='pw')
        RoomInvitation.objects.create(room=self.room, invited_user=target, invited_by=self.owner, role='student', status='pending')
        self.client.force_login(target)
        resp = self.client.get(reverse('room:invitations'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.room.name)
        self.assertContains(resp, 'Pending')
