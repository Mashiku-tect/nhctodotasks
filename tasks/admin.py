# tasks/admin.py
from django.contrib import admin
from .models import Task, UserTask, SubTask,TaskAttachment


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'due_date', 'created_at', 'updated_at')
    search_fields = ('title',)
    list_filter = ('due_date',)
    ordering = ('-created_at',)


@admin.register(UserTask)
class UserTaskAdmin(admin.ModelAdmin):
    list_display = (
        'task',
        'assigned_to',
        'assigned_by',
        'status',
        'created_at',
        'completed_at',
    )
    list_filter = ('status', 'assigned_to')
    search_fields = ('task__title', 'assigned_to__email')
    autocomplete_fields = ('task', 'assigned_to', 'assigned_by')
    ordering = ('-created_at',)


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'task', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'task__title')
    autocomplete_fields = ('task',)


#register the attachment model 
@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'task',
        'uploaded_by',
        'file',
        'created_at',
    )

    list_filter = (
        'created_at',
        'uploaded_by'
    )

    search_fields = (
        'task__title',
        'uploaded_by__email',
    )

    readonly_fields = (
        'created_at',
    )


from django.contrib import admin
from .models import Comment

class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'parent','comment', 'created_at')  # columns shown in list view
    list_filter = ('created_at', 'user')  # add filters in the sidebar
    search_fields = ('user__email', 'comment', 'task__title')  # search bar fields
    readonly_fields = ('created_at',)  # prevent editing created_at

admin.site.register(Comment, CommentAdmin)
