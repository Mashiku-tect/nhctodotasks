from django.urls import path
from .views import create_task, staff_detail,category_users_json,staff_task_detail,manager_task_detail, due_soon_report,do_task,my_tasks,assigned_tasks, overdue_tasks_report, reassign_task, staff_performance_report,task_detail,start_task,complete_subtask,complete_task,edit_task,delete_task,delete_subtask,review_task,reply_comment,ajax_save_subtask,subtask_json,delete_task_cascade
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create/', create_task, name='create_task'),
     path('mytasks/', my_tasks, name='my_tasks'),
     path('assigned/', assigned_tasks, name='assigned_tasks'),
    #   path('', dashboard, name='dashboard'),
      path('tasks/<int:task_id>/', task_detail, name='task_detail'),
      path('tasks/<int:task_id>/', do_task, name='do_task'),
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
   
path('reports/due-soon/', due_soon_report, name='reports_due_soon'),
path('reports/staff-performance/', staff_performance_report, name='reports_performance'),
 path('task/<int:task_id>/reassign/', reassign_task, name='reassign_task'),

path('staff/<int:staff_id>/', staff_detail, name='staff_detail'),
 path('manager-task/<int:staff_id>/', manager_task_detail, name='manager_task_detail'),  # ✅ add this
 path('staff-task/<int:staff_id>/', staff_task_detail, name='staff_task_detail'),
 path('category-users/', category_users_json, name='category_users_json'),

]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)