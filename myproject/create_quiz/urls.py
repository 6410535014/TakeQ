from django.urls import path
from . import views

app_name = "create_quiz"

urlpatterns = [
	path("", views.QuizListView.as_view(), name="quiz_list"),
	path("create/", views.QuizCreateView.as_view(), name="quiz_create"),
	path("<int:pk>/edit/", views.QuizUpdateView.as_view(), name="quiz_edit"),
	path("<int:pk>/detail/", views.QuizDetailView.as_view(), name="quiz_detail"),
	path("<int:quiz_id>/questions/add/", views.add_question, name="add_question"),
	path("questions/<int:pk>/edit/", views.edit_question, name="edit_question"),
	path("<int:pk>/publish-toggle/", views.toggle_publish, name="toggle_publish"),
    path("<int:pk>/delete/", views.QuizDeleteView.as_view(), name="quiz_delete"),
    path("<int:quiz_id>/reorder/", views.reorder_questions, name="reorder_questions"),
]
