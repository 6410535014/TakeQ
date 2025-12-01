from django.urls import path
from . import views

app_name = 'room'

urlpatterns = [
	path('create/', views.CreateRoomView.as_view(), name='create'),
	path('detail/<str:code>/', views.RoomDetailView.as_view(), name='detail'),
    path('detail/<str:code>/members/', views.ManageMembersView.as_view(), name='manage_members'),
    path('detail/<str:code>/members/change-role/', views.ChangeMemberRoleView.as_view(), name='change_member_role'),
	path('detail/<str:code>/members/remove/', views.RemoveMemberView.as_view(), name='remove_member'),
	path('join/', views.JoinByCodeView.as_view(), name='join_by_code'),
	path('invite/<str:code>/', views.InviteUserView.as_view(), name='invite'),
	path('invitations/', views.InvitationsListView.as_view(), name='invitations'),
	path('invitation/<int:pk>/<str:action>/', views.InvitationResponseView.as_view(), name='invitation_response'),
	path('assign_quiz/<str:code>/', views.AssignQuizToRoomView.as_view(), name='assign_quiz'),
    path('detail/<str:code>/delete/', views.DeleteRoomView.as_view(), name='delete'),
]
