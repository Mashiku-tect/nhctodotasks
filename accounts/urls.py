# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('add-user/', views.add_user, name='add_user'),
    path("login/", views.login_view, name="login"),
  
    path("logout/", views.logout_view, name="logout"),
]
