
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include("myapp.urls")),
    path('take/', include(("take_quiz.urls", "take_quiz"), namespace="take_quiz")),
    path('create/', include(("create_quiz.urls", "create_quiz"), namespace="create_quiz"))
]
