# accounts/urls.py
from django.urls import path
from . import views
from tasks.views import staff_performance_report

urlpatterns = [
    path('add-user/', views.add_user, name='add_user'),
    path('manage/', views.manage_users, name='manage_users'),
    path('user/<int:user_id>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),
    path('user/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path("login/", views.login_view, name="login"),
    path('reports/staff-performance/', staff_performance_report, name='reports_performance'),
    path("logout/", views.logout_view, name="logout"),
]
