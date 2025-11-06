from django.urls import path
from myapp import views, views_auth

urlpatterns = [
    path('', views.home, name='home'),
    path('about', views.about, name='about'),
    path('register', views_auth.register_view, name='register'),
    path('login', views_auth.login_view, name='login'),
    path('logout', views_auth.logout_view, name='logout'),
]