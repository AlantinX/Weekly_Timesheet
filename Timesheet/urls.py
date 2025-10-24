from django.urls import path
from . import views

app_name = 'Timesheet'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('crew/', views.crew_list, name='crew_list'),
    path('employees/<int:pk>/delete/', views.delete_employee, name='delete_employee'),
    path('timesheet/new/', views.new_timesheet, name='new_timesheet'),
    path('timesheet/<int:pk>/', views.view_timesheet, name='view_timesheet'),
    path('timesheet/<int:pk>/edit/', views.edit_timesheet, name='edit_timesheet'),
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:pk>/reactivate/', views.reactivate_user, name='reactivate_user'),
    path('employees/<int:pk>/reactivate/', views.reactivate_employee, name='reactivate_employee'),
    path('users/<int:pk>/unlock/', views.unlock_user, name='unlock_user'),
]
