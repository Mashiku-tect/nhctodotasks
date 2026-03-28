# tasks/admin.py
from django.contrib import admin
from .models import Task, UserTask, SubTask, TaskAttachment, Comment, Category, CategoryMember, Notification


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'due_date', 'created_at', 'updated_at')
    search_fields = ('title',)
    list_filter = ('due_date',)
    ordering = ('-created_at',)

from django.contrib import admin
from .models import Category, CategoryMember
from accounts.models import User

class CategoryMemberInline(admin.TabularInline):
    model = CategoryMember
    extra = 1  # number of blank forms
    autocomplete_fields = ('user',)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        parent_obj = getattr(self, 'parent_obj', None)
        if db_field.name == 'user' and parent_obj is not None:
            # limit users to the selected section
            kwargs['queryset'] = User.objects.filter(section=parent_obj.section)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'section')
    inlines = [CategoryMemberInline]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # store obj for inline filtering
        CategoryMemberInline.parent_obj = obj
        return form

admin.site.register(Category, CategoryAdmin)

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




class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'parent','comment', 'created_at')  # columns shown in list view
    list_filter = ('created_at', 'user')  # add filters in the sidebar
    search_fields = ('user__email', 'comment', 'task__title')  # search bar fields
    readonly_fields = ('created_at',)  # prevent editing created_at

admin.site.register(Comment, CommentAdmin)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__email', 'title', 'message', 'task__title')
