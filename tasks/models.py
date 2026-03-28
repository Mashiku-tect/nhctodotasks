from django.db import models
from django.contrib.auth import get_user_model

from django.conf import settings
from django.core.exceptions import ValidationError
from accounts.models import User

User = get_user_model()
#User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=100)
    section = models.CharField(
        max_length=100,
        choices=User.SECTION_CHOICES
    )
    members = models.ManyToManyField(
        User,
        through='CategoryMember',
        related_name='categories_joined'  # avoid clash
    )

    def __str__(self):
        return f"{self.name} ({self.section})"


class Category(models.Model):
    name = models.CharField(max_length=100)
    section = models.CharField(
        max_length=100,
        choices=User.SECTION_CHOICES
    )

    members = models.ManyToManyField(
        User,
        through='CategoryMember',   # through table
        related_name='categories'   # reverse lookup from User
    )

    def __str__(self):
        return f"{self.name} ({self.section})"


class CategoryMember(models.Model):
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE,
        related_name='category_members'  # avoids clashes
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('category', 'user')

    def __str__(self):
        return f"{self.category.name} → {self.user.email}"
    
class Task(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
    ]
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to='task_files/', blank=True, null=True)
    due_date = models.DateField()
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name='completed_tasks'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class UserTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('rejected', 'Rejected'),
        ('accepted', 'Accepted'),
    ]
    

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='user_tasks'
    )
    review_status = models.CharField(
    max_length=20,
    choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ],
    default='pending'
)


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tasks_assigned'
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tasks_received'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.task.title} → {self.assigned_to}"


class TaskReportRecord(models.Model):
    source_usertask_id = models.PositiveIntegerField(unique=True)
    source_task_id = models.PositiveIntegerField(db_index=True)

    task_title = models.CharField(max_length=255)
    task_description = models.TextField(blank=True)
    category_name = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=100, blank=True)
    priority = models.CharField(max_length=20, blank=True)
    due_date = models.DateField(null=True, blank=True)

    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_report_records_assigned'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_report_records_received'
    )
    assigned_by_username = models.CharField(max_length=150, blank=True)
    assigned_to_username = models.CharField(max_length=150, blank=True)

    status = models.CharField(max_length=20, choices=UserTask.STATUS_CHOICES, default='pending')
    review_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    is_self_task = models.BooleanField(default=False)

    task_created_at = models.DateTimeField(null=True, blank=True)
    task_updated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_username = models.CharField(max_length=150, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-task_created_at', '-last_synced_at']

    def __str__(self):
        return f"{self.task_title} -> {self.assigned_to_username or 'unknown'}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('task_assigned', 'Task Assigned'),
        ('task_review', 'Task Review'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES
    )
    target_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.title}"


#subtasks model
class SubTask(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='subtasks'
    )

    created_by = models.ForeignKey(User, on_delete=models.CASCADE,null=True,   # TEMPORARY
    blank=True)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.task.title} → {self.title}"
    

#comments(reasons) model
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField()

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.email}"


#attachements model
class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments'
    )

    file = models.FileField(
        upload_to='task_attachments/'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """
        Enforce max 3 attachments per task
        """
        if self.task.attachments.count() >= 3 and not self.pk:
            raise ValidationError(
                "A task can have a maximum of 3 attachments."
            )

    def save(self, *args, **kwargs):
        self.full_clean()  # calls clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment for {self.task.title}"
