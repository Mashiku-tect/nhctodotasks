from django import views
from django.urls import path
from .views import create_task, due_soon_report,my_tasks,assigned_tasks,dashboard, overdue_tasks_report, staff_performance_report,task_detail,start_task,complete_subtask,complete_task,edit_task,delete_task,delete_subtask,review_task,reply_comment,ajax_save_subtask,subtask_json,delete_task_cascade
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create/', create_task, name='create_task'),
     path('mytasks/', my_tasks, name='my_tasks'),
     path('assigned/', assigned_tasks, name='assigned_tasks'),
      path('', dashboard, name='dashboard'),
      path('tasks/<int:task_id>/', task_detail, name='task_detail'),
path('tasks/start/<int:usertask_id>/', start_task, name='start_task'),
path('tasks/complete/<int:task_id>/', complete_task, name='complete_task'),
#path('subtasks/complete/<int:subtask_id>/', complete_subtask, name='complete_subtask'),
path('tasks/<int:task_id>/edit/', edit_task, name='edit_task'),
path('tasks/<int:task_id>/delete/', delete_task, name='delete_task'),
#path('subtasks/<int:subtask_id>/edit/', edit_subtask, name='edit_subtask'),
#path('subtasks/<int:subtask_id>/delete/', delete_subtask, name='delete_subtask'),
 path(
        'tasks/<int:task_id>/review/',
        review_task,
        name='review_task'
    ),
       # Add a major comment (manager only)
    path('tasks/<int:comment_id>/reply-comment/', reply_comment, name='reply_comment'),
    path('tasks/<int:task_id>/subtask/save/', ajax_save_subtask, name='ajax_save_subtask'),
    path('subtasks/<int:subtask_id>/json/', subtask_json),
    path('subtasks/<int:subtask_id>/complete/', complete_subtask),
path('subtasks/<int:subtask_id>/delete/', delete_subtask),
path(
    'tasks/delete-task/<int:task_id>/',
    delete_task_cascade,
    name='delete_task_cascade'
),
     path('reports/overdue/',overdue_tasks_report, name='reports_overdue'),
     # urls.py
path('reports/due-soon/', due_soon_report, name='reports_due_soon'),
path('reports/staff-performance/', staff_performance_report, name='reports_performance'),
]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)