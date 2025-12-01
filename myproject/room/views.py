from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from .models import Room, RoomMembership, RoomInvitation, RoomQuizAssignment
from .forms import RoomCreateForm, JoinRoomByCodeForm, InviteForm
from django.contrib import messages
from django.contrib.auth import get_user_model
from myapp.models import Quiz
from django.utils import timezone

User = get_user_model()

def user_role_in_room(user, room):
	try:
		m = RoomMembership.objects.get(user=user, room=room)
		return m.role
	except RoomMembership.DoesNotExist:
		return None

class CreateRoomView(LoginRequiredMixin, View):
	def get(self, request):
		form = RoomCreateForm()
		return render(request, 'room/create_room.html', {'form': form})

	def post(self, request):
		form = RoomCreateForm(request.POST)
		if form.is_valid():
			room = form.save(commit=False)
			room.owner = request.user
			room.save()
			RoomMembership.objects.create(room=room, user=request.user, role=RoomMembership.ROLE_OWNER)
			return redirect('home')
		return render(request, 'room/create_room.html', {'form': form})

class RoomDetailView(LoginRequiredMixin, View):
    def get(self, request, code):
        room = get_object_or_404(Room, code=code)
        role = user_role_in_room(request.user, room)
        members = room.memberships.select_related('user').all()
        assignments = room.assignments.select_related('quiz').all()  

        assigned_quizzes = [a.quiz for a in assignments]

        owner_quizzes = []
        if role in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
            owner_quizzes_qs = Quiz.objects.filter(creator=request.user).order_by('-created_at')
            assigned_ids = [q.pk for q in assigned_quizzes]
            owner_quizzes = owner_quizzes_qs.exclude(pk__in=assigned_ids)

        visible_assigned_for_students = [q for q in assigned_quizzes if q.is_published]

        return render(request, 'room/detail.html', {
            'room': room,
            'role': role,
            'members': members,
            'assignments': assignments,
            'assigned_quizzes': assigned_quizzes,
            'owner_quizzes': owner_quizzes,
            'visible_assigned_for_students': visible_assigned_for_students,
        })

class JoinByCodeView(LoginRequiredMixin, View):
	def post(self, request):
		form = JoinRoomByCodeForm(request.POST)
		if not form.is_valid():
			return redirect('/')
		code = form.cleaned_data['code'].upper()
		room = get_object_or_404(Room, code=code)
		if RoomMembership.objects.filter(room=room, user=request.user).exists():
			return redirect('room:detail', code=room.code)
		RoomMembership.objects.create(room=room, user=request.user, role=RoomMembership.ROLE_STUDENT)
		return redirect('room:detail', code=room.code)

class InviteUserView(LoginRequiredMixin, View):
    def post(self, request, code):
        form = InviteForm(request.POST)
        room = get_object_or_404(Room, code=code)
        role = user_role_in_room(request.user, room)

        if role not in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
            return HttpResponseForbidden()

        if not form.is_valid():
            messages.error(request, "Invalid data")
            return redirect('room:detail', code=room.code)

        username_or_email = form.cleaned_data['username']
        invite_role = form.cleaned_data['role']  # 'admin' or 'student'

        if role == RoomMembership.ROLE_ADMIN and invite_role == 'admin':
            return HttpResponseForbidden()

        try:
            target = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            try:
                target = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                messages.error(request, 'User not found')
                return redirect('room:detail', code=room.code)

        if RoomMembership.objects.filter(room=room, user=target).exists():
            messages.info(request, 'User already a member')
            return redirect('room:detail', code=room.code)

        inv, created = RoomInvitation.objects.update_or_create(
            room=room,
            invited_user=target,
            defaults={
                'invited_by': request.user,
                'role': invite_role,
                'status': 'pending',
                'message': form.cleaned_data.get('message', '') if hasattr(form, 'cleaned_data') else '',
                'created_at': timezone.localtime(timezone.now()),   
            }
        )

        if created:
            messages.success(request, f'Invitation sent to {target}')
        else:
            messages.info(request, f'Invitation already exists for {target}')

        return redirect('room:detail', code=room.code)

class InvitationResponseView(LoginRequiredMixin, View):
	def post(self, request, pk, action):
		inv = get_object_or_404(RoomInvitation, pk=pk, invited_user=request.user)
		if inv.status != RoomInvitation.STATUS_PENDING:
			return redirect('room:invitations')
		if action == 'accept':
			inv.accept()
		else:
			inv.decline()
		return redirect('room:invitations')

class InvitationsListView(LoginRequiredMixin, View):
	def get(self, request):
		invs = RoomInvitation.objects.filter(invited_user=request.user).order_by('-created_at')
		return render(request, 'room/invitations_list.html', {'invitations': invs})

class AssignQuizToRoomView(LoginRequiredMixin, View):
	def post(self, request, code):
		room = get_object_or_404(Room, code=code)
		role = user_role_in_room(request.user, room)
		if role not in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
			return HttpResponseForbidden()
		quiz_id = int(request.POST.get('quiz_id'))
		from myapp.models import Quiz
		quiz = Quiz.objects.filter(pk=quiz_id).first()
		if not quiz:
			messages.error(request, 'Quiz not found')
			return redirect('room:detail', code=room.code)
		RoomQuizAssignment.objects.get_or_create(room=room, quiz=quiz, defaults={'assigned_by': request.user})
		return redirect('room:detail', code=room.code)
	
class DeleteRoomView(LoginRequiredMixin, View):
    def post(self, request, code):
        room = get_object_or_404(Room, code=code)
        if room.owner != request.user:
            return HttpResponseForbidden()
        room.delete()
        messages.success(request, 'Room deleted.')
        return redirect('/')  


class ManageMembersView(LoginRequiredMixin, View):
    def get(self, request, code):
        room = get_object_or_404(Room, code=code)
        role = user_role_in_room(request.user, room)

        members_qs = RoomMembership.objects.filter(room=room).select_related('user').order_by('role', 'user__username')
        owners = [m for m in members_qs if m.role == RoomMembership.ROLE_OWNER]
        admins = [m for m in members_qs if m.role == RoomMembership.ROLE_ADMIN]
        students = [m for m in members_qs if m.role == RoomMembership.ROLE_STUDENT]

        invite_form = InviteForm()

        is_owner = (role == RoomMembership.ROLE_OWNER or role == 'owner')
        is_admin = (role == RoomMembership.ROLE_ADMIN or role == 'admin')

        return render(request, 'room/manage_members.html', {
            'room': room,
            'role': role,
            'owners': owners,
            'admins': admins,
            'students': students,
            'invite_form': invite_form,
            'is_owner': is_owner,
            'is_admin': is_admin,
        })

    def post(self, request, code):
        room = get_object_or_404(Room, code=code)
        role = user_role_in_room(request.user, room)
        if role not in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
            return HttpResponseForbidden()

        form = InviteForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid input")
            return redirect('room:manage_members', code=room.code)

        username_or_email = form.cleaned_data['username']
        invite_role = form.cleaned_data['role']

        if role == RoomMembership.ROLE_ADMIN and invite_role == 'admin':
            return HttpResponseForbidden()

        try:
            target = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            try:
                target = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                messages.error(request, 'User not found')
                return redirect('room:manage_members', code=room.code)

        if RoomMembership.objects.filter(room=room, user=target).exists():
            messages.info(request, 'User already a member')
            return redirect('room:manage_members', code=room.code)


        inv, created = RoomInvitation.objects.update_or_create(
            room=room,
            invited_user=target,
            defaults={
                'invited_by': request.user,
                'role': invite_role,
                'status': 'pending',
                'message': form.cleaned_data.get('message', '') if hasattr(form, 'cleaned_data') else '',
                'created_at': timezone.localtime(timezone.now()),  
            }
        )

        if created:
            messages.success(request, f'Invitation sent to {target.username}')
        else:
            messages.info(request, f'Invitation already exists for {target.username}')

        return redirect('room:manage_members', code=room.code)


class RemoveMemberView(LoginRequiredMixin, View):
    def post(self, request, code):
        room = get_object_or_404(Room, code=code)
        role = user_role_in_room(request.user, room)
        if role not in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
            return HttpResponseForbidden()

        member_user_id = request.POST.get('member_user_id')
        if not member_user_id:
            messages.error(request, 'Missing member id')
            return redirect('room:manage_members', code=room.code)

        try:
            member_user = User.objects.get(pk=int(member_user_id))
        except User.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('room:manage_members', code=room.code)

        try:
            membership = RoomMembership.objects.get(room=room, user=member_user)
        except RoomMembership.DoesNotExist:
            messages.error(request, 'User is not a member')
            return redirect('room:manage_members', code=room.code)

        if membership.role == RoomMembership.ROLE_OWNER:
            messages.error(request, 'Cannot remove the owner')
            return redirect('room:manage_members', code=room.code)

        if role == RoomMembership.ROLE_ADMIN and membership.role != RoomMembership.ROLE_STUDENT:
            return HttpResponseForbidden()

        membership.delete()
        messages.success(request, f'{member_user.username} removed from the room')
        return redirect('room:manage_members', code=room.code)

class ChangeMemberRoleView(LoginRequiredMixin, View):
    def post(self, request, code):
        room = get_object_or_404(Room, code=code)
        actor_role = user_role_in_room(request.user, room)
        if actor_role != RoomMembership.ROLE_OWNER:
            return HttpResponseForbidden()

        member_user_id = request.POST.get('member_user_id')
        new_role = request.POST.get('new_role')  # expected 'admin' or 'student'
        if not member_user_id or new_role not in ('admin', 'student'):
            messages.error(request, 'Invalid request')
            return redirect('room:manage_members', code=room.code)

        try:
            target = User.objects.get(pk=int(member_user_id))
        except User.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('room:manage_members', code=room.code)

        try:
            membership = RoomMembership.objects.get(room=room, user=target)
        except RoomMembership.DoesNotExist:
            messages.error(request, 'User is not a member of this room')
            return redirect('room:manage_members', code=room.code)

        if target == room.owner:
            messages.error(request, 'Cannot change owner role')
            return redirect('room:manage_members', code=room.code)

        if new_role == 'admin':
            membership.role = RoomMembership.ROLE_ADMIN
        else:
            membership.role = RoomMembership.ROLE_STUDENT
        membership.save()
        messages.success(request, f'{target.username} is now {new_role}')
        return redirect('room:manage_members', code=room.code)


class RemoveMemberView(LoginRequiredMixin, View):
    def post(self, request, code):
        room = get_object_or_404(Room, code=code)
        actor_role = user_role_in_room(request.user, room)
        if actor_role not in (RoomMembership.ROLE_OWNER, RoomMembership.ROLE_ADMIN):
            return HttpResponseForbidden()

        member_user_id = request.POST.get('member_user_id')
        if not member_user_id:
            messages.error(request, 'Missing member id')
            return redirect('room:manage_members', code=room.code)

        try:
            target = User.objects.get(pk=int(member_user_id))
        except User.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('room:manage_members', code=room.code)

        try:
            membership = RoomMembership.objects.get(room=room, user=target)
        except RoomMembership.DoesNotExist:
            messages.error(request, 'User is not a member')
            return redirect('room:manage_members', code=room.code)

        if membership.role == RoomMembership.ROLE_OWNER:
            messages.error(request, 'Cannot remove the owner')
            return redirect('room:manage_members', code=room.code)

        if actor_role == RoomMembership.ROLE_ADMIN and membership.role != RoomMembership.ROLE_STUDENT:
            return HttpResponseForbidden()

        membership.delete()
        messages.success(request, f'{target.username} removed from the room')
        return redirect('room:manage_members', code=room.code)
