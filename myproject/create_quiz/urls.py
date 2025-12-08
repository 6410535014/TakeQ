from django.urls import path
from . import views

app_name = "create_quiz"

urlpatterns = [
	path("", views.QuizListView.as_view(), name="quiz_list"),
	path("create/", views.QuizCreateView.as_view(), name="quiz_create"),
    path("create/<str:room_code>/", views.QuizCreateView.as_view(), name="quiz_create_for_room"),
	path("<int:pk>/edit/", views.QuizUpdateView.as_view(), name="quiz_edit"),
	path("<int:pk>/detail/", views.QuizDetailView.as_view(), name="quiz_detail"),
	path("<int:quiz_id>/questions/add/", views.add_question, name="add_question"),
	path("questions/<int:pk>/edit/", views.edit_question, name="edit_question"),
	path("<int:pk>/publish-toggle/", views.toggle_publish, name="toggle_publish"),
    path("<int:quiz_id>/reorder/", views.reorder_questions, name="reorder_questions"),
    path('question/<int:pk>/delete/', views.delete_question, name='delete_question'),
    path('<int:pk>/attempts/', views.QuizAttemptsListView.as_view(), name='quiz_attempts'),
    path('attempt/<int:attempt_id>/detail/', views.attempt_detail, name='attempt_detail'),
	path('<int:pk>/delete/', views.quiz_delete, name='quiz_delete'),
]
