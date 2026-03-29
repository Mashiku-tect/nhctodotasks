import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Task, UserTask, SubTask, Comment, TaskAttachment, Category, Notification, TaskReportRecord
from django.utils import timezone
from django.http import HttpResponseForbidden,JsonResponse
from django.db.models import F, Q
from collections import defaultdict
from django.views.decorators.http import require_POST
import os
from django.utils import timezone
import pytz
from django.core.paginator import Paginator
from datetime import date

tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
today = timezone.now().astimezone(tanzania_tz).date()


User = get_user_model()

def compute_task_status(usertasks):
    statuses = {ut.status for ut in usertasks}

    if statuses == {'completed'}:
        return 'completed'
    elif statuses == {'rejected'}:
        return 'rejected'
    elif statuses == {'in_progress'}:
        return 'in_progress'
    else:
        return 'pending'



from django.urls import reverse


def create_notification(*, user, title, message, notification_type, task=None, target_url=''):
    Notification.objects.create(
        user=user,
        task=task,
        title=title,
        message=message,
        notification_type=notification_type,
        target_url=target_url,
    )


def sync_task_report_records(task=None, usertasks=None, mark_deleted=False):
    if usertasks is None:
        if task is None:
            return
        usertasks = task.user_tasks.select_related('assigned_by', 'assigned_to', 'task', 'task__category')

    deleted_at = timezone.now() if mark_deleted else None

    for ut in usertasks:
        task_obj = ut.task
        assigned_by = ut.assigned_by
        assigned_to = ut.assigned_to

        TaskReportRecord.objects.update_or_create(
            source_usertask_id=ut.id,
            defaults={
                'source_task_id': task_obj.id,
                'task_title': task_obj.title,
                'task_description': task_obj.description or '',
                'category_name': task_obj.category.name if task_obj.category else '',
                'section': getattr(assigned_to, 'section', '') or getattr(assigned_by, 'section', ''),
                'priority': task_obj.priority,
                'due_date': task_obj.due_date,
                'assigned_by': assigned_by,
                'assigned_to': assigned_to,
                'assigned_by_username': getattr(assigned_by, 'username', '') if assigned_by else '',
                'assigned_to_username': getattr(assigned_to, 'username', '') if assigned_to else '',
                'status': ut.status,
                'review_status': ut.review_status,
                'is_self_task': assigned_by_id_equals(assigned_by, assigned_to),
                'task_created_at': task_obj.created_at,
                'task_updated_at': task_obj.updated_at,
                'completed_at': ut.completed_at or task_obj.completed_at,
                'completed_by_username': getattr(task_obj.completed_by, 'username', '') if task_obj.completed_by else '',
                'deleted_at': deleted_at,
            }
        )


def assigned_by_id_equals(assigned_by, assigned_to):
    if not assigned_by or not assigned_to:
        return False
    return assigned_by.id == assigned_to.id

@login_required
def create_task(request):
    user = request.user
    subordinates = []
    categories = []
    category = None

    # Load form data
    if user.role == 'manager':
        categories = Category.objects.filter(section=user.section)

        subordinates = User.objects.filter(
            section=user.section,
            role='staff',
            is_active=True
        )

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        attachment = request.FILES.get("attachment")
        due_date = request.POST.get('due_date')
        priority = request.POST.get('priority', 'normal')
        category_id = request.POST.get('category_id')
        selected_user_ids = request.POST.getlist('assigned_to[]')

        if not title or not due_date:
            return JsonResponse(
                {'error': 'Title and due date are required.'},
                status=400
            )

        # 🔹 Default: self task
        assigned_users = [user]
        redirect_url = reverse('my_tasks')

        # 🔹 Manager assigning by category
        if user.role == 'manager' and category_id:
            category = Category.objects.filter(
                id=category_id,
                section=user.section
            ).first()

            if not category:
                return JsonResponse({'error': 'Invalid category'}, status=400)

            assigned_users = User.objects.filter(
                id__in=selected_user_ids,
                role='staff',
                section=user.section,
                is_active=True,
                categorymember__category=category
            ).distinct()

            if not assigned_users.exists():
                return JsonResponse({'error': 'Select at least one valid staff member from this category'}, status=400)

            redirect_url = reverse('assigned_tasks')

        # 🔹 Create Task
        task = Task.objects.create(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            attachment=attachment,
            category=category
        )

       # 🔹 Assign Users
        UserTask.objects.bulk_create([
            UserTask(
                task=task,
                assigned_by=user,
                assigned_to=assignee,
                status='pending'
            )
            for assignee in assigned_users
        ])
        sync_task_report_records(task=task)

        if user.role == 'manager':
            target_url = reverse('task_detail', args=[task.id])
            for assignee in assigned_users:
                if assignee != user:
                    create_notification(
                        user=assignee,
                        title='New task assigned',
                        message=f'You have been assigned a new task: {task.title}.',
                        notification_type='task_assigned',
                        task=task,
                        target_url=target_url,
                    )

        # ✅ Add success message
        if assigned_users == [user]:
            messages.success(request, "My task created successfully!")
        else:
            messages.success(request, "Task assigned successfully!")

        # ✅ Return JSON with redirect URL
        return JsonResponse({
            'message': 'success',
            'redirect_url': redirect_url
        })
    return render(
        request,
        'tasks/create_task.html',
        {
            'subordinates': subordinates,
            'categories': categories,
            'PRIORITY_CHOICES': Task.PRIORITY_CHOICES,
        }
    )

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from datetime import date

from .models import UserTask


@login_required
def my_tasks(request):
    user = request.user

    # Get filter values
    status_filter  = request.GET.get('status')
    review_filter  = request.GET.get('review')
    due_filter     = request.GET.get('due')
    search_query   = request.GET.get('q', '').strip()

    # Base queryset: only tasks user created AND assigned to themselves
    qs = UserTask.objects.filter(
        assigned_by=user,
        assigned_to=user
    ).select_related('task')

    # Apply search
    if search_query:
        qs = qs.filter(task__title__icontains=search_query)

    # Apply due date filter
    today = date.today()
    if due_filter == 'today':
        qs = qs.filter(task__due_date=today)
    elif due_filter == 'overdue':
        qs = qs.filter(task__due_date__lt=today)
    elif due_filter == 'upcoming':
        qs = qs.filter(task__due_date__gt=today)

    # Apply status filter
    if status_filter in ['pending', 'in_progress', 'completed']:
        qs = qs.filter(status=status_filter)

    # Apply review filter
    if review_filter in ['pending', 'accepted', 'rejected']:
        qs = qs.filter(review_status=review_filter)

    # Order by most recent first
    qs = qs.order_by('-created_at')

    # Extract unique tasks (since UserTask → Task is 1:1 in this case)
    tasks_list = []
    for ut in qs:
        task = ut.task
        task.user_task = ut
        task.days_left = (task.due_date - today).days if task.due_date else None
        tasks_list.append(task)

    # Pagination (10 per page)
    paginator = Paginator(tasks_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'tasks': page_obj,  # keep 'tasks' for backward compatibility if needed
        'current_filters': {
            'status': status_filter,
            'review': review_filter,
            'due': due_filter,
            'q': search_query,
        }
    }

    return render(request, 'tasks/my_tasks.html', context)


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from collections import defaultdict
from django.core.paginator import Paginator
from datetime import date
import pytz
from django.utils import timezone

from .models import UserTask, Task


@login_required
def assigned_tasks(request):
    user = request.user

    status_filter = request.GET.get('status')
    review_filter = request.GET.get('review')
    due_filter    = request.GET.get('due')
    search_query  = request.GET.get('q', '').strip()

    # Base queryset – tasks visible to current user
    if user.role == 'staff':
        visible_qs = UserTask.objects.filter(
            assigned_to=user
        ).exclude(
            assigned_by=user          # exclude self-created tasks
        ).select_related('task', 'assigned_by', 'assigned_to')
    else:  # manager
        visible_qs = UserTask.objects.filter(
            assigned_by=user
        ).exclude(
            assigned_to=user          # exclude self-tasks
        ).select_related('task', 'assigned_by', 'assigned_to')

    # Apply search
    if search_query:
        visible_qs = visible_qs.filter(task__title__icontains=search_query)

    # Apply due date filter
    today = date.today()
    if due_filter == 'today':
        visible_qs = visible_qs.filter(task__due_date=today)
    elif due_filter == 'overdue':
        visible_qs = visible_qs.filter(task__due_date__lt=today)
    elif due_filter == 'upcoming':
        visible_qs = visible_qs.filter(task__due_date__gt=today)

    # Apply status filter
    if status_filter in ['pending', 'in_progress', 'completed']:
        visible_qs = visible_qs.filter(status=status_filter)

    # Apply review filter
    if review_filter in ['pending', 'accepted', 'rejected']:
        visible_qs = visible_qs.filter(review_status=review_filter)

    # ───────────────────────────────────────────────
    # Grouping and task enrichment (unchanged)
    # ───────────────────────────────────────────────
    grouped_tasks = defaultdict(list)
    for ut in visible_qs:
        grouped_tasks[ut.task].append(ut)

    task_list = []
    for task, usertasks in grouped_tasks.items():
        if user.role == 'manager':
            all_usertasks = task.user_tasks.select_related('assigned_to', 'assigned_by') \
                                           .exclude(Q(assigned_to=user) & Q(assigned_by=user))
            own_usertask = all_usertasks.filter(assigned_to=user).first()
            display_usertasks = all_usertasks
            computed_status = compute_task_status(all_usertasks)
        else:
            own_usertask = next((ut for ut in usertasks if ut.assigned_to_id == user.id), None)
            display_usertasks = task.user_tasks.select_related('assigned_to', 'assigned_by').all()
            computed_status = own_usertask.status if own_usertask else compute_task_status(usertasks)

        days_left = (task.due_date - today).days
        is_overdue = days_left < 0 and computed_status in ['pending', 'in_progress']
        reassign_needed = is_overdue

        if is_overdue:
            days_left = 0

        start_date = task.created_at.date()
        end_date = task.due_date
        total_days = (end_date - start_date).days or 1  # avoid division by zero
        days_passed = (today - start_date).days
        deadline_progress = min(max(int((days_passed / total_days) * 100), 0), 100)

        task_dict = {
            "task": task,
            "usertasks": display_usertasks,
            "own_usertask": own_usertask,
            "computed_status": computed_status,
            "days_left": days_left,
            "is_overdue": is_overdue,
            "reassign_needed": reassign_needed,
            "deadline_progress": deadline_progress,
            "completed_by": task.completed_by,
        }
        task_list.append(task_dict)

    # Keep newly created or recently edited tasks visible at the top
    task_list.sort(key=lambda x: x['task'].updated_at, reverse=True)

    paginator = Paginator(task_list, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'task_list': page_obj,
        'page_obj': page_obj,
        'current_filters': {
            'status': status_filter,
            'review': review_filter,
            'due': due_filter,
            'q': search_query,
        }
    }

    return render(request, 'tasks/assigned_tasks.html', context)


def filter_task_report_records(records, request):
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    status = request.GET.get('status', '').strip()
    deleted = request.GET.get('deleted', '').strip()
    query = request.GET.get('q', '').strip()

    if date_from:
        records = records.filter(task_created_at__date__gte=date_from)
    if date_to:
        records = records.filter(task_created_at__date__lte=date_to)
    if status:
        records = records.filter(status=status)
    if deleted == 'active':
        records = records.filter(deleted_at__isnull=True)
    elif deleted == 'deleted':
        records = records.filter(deleted_at__isnull=False)
    if query:
        records = records.filter(
            Q(task_title__icontains=query) |
            Q(category_name__icontains=query) |
            Q(assigned_by_username__icontains=query) |
            Q(assigned_to_username__icontains=query)
        )

    return records.order_by('-task_created_at', '-last_synced_at'), {
        'date_from': date_from,
        'date_to': date_to,
        'status': status,
        'deleted': deleted,
        'q': query,
    }


@login_required
def my_task_report(request):
    records = TaskReportRecord.objects.filter(
        assigned_by=request.user,
        assigned_to=request.user,
    )
    records, filters = filter_task_report_records(records, request)

    return render(request, 'reports/task_history_report.html', {
        'report_title': 'My Task Report',
        'report_subtitle': 'History of tasks you created for yourself, including deleted records.',
        'records': records,
        'filters': filters,
        'report_kind': 'my',
        'show_counterparty': False,
    })


@login_required
def reports_home(request):
    report_cards = [
        {
            'title': 'My Task Report',
            'description': 'See the history of tasks you created for yourself.',
            'icon': 'bi-file-earmark-text',
            'url': reverse('report_my_tasks'),
        },
        {
            'title': 'Assigned Report',
            'description': 'Review tasks shared between you and other staff members.',
            'icon': 'bi-journal-check',
            'url': reverse('report_assigned_tasks'),
        },
    ]

    if request.user.role == 'manager':
        report_cards.extend([
            {
                'title': 'Overdue Tasks',
                'description': 'Focus on work that has passed the deadline and needs follow-up.',
                'icon': 'bi-exclamation-circle',
                'url': reverse('reports_overdue'),
            },
            {
                'title': 'Due Soon',
                'description': 'Catch tasks approaching the deadline before they become overdue.',
                'icon': 'bi-clock',
                'url': reverse('reports_due_soon'),
            },
        ])

    return render(request, 'reports/reports_home.html', {
        'report_cards': report_cards,
        'show_performance_link': request.user.role == 'manager' or request.user.is_superuser,
    })


@login_required
def assigned_task_report(request):
    if request.user.role == 'manager':
        records = TaskReportRecord.objects.filter(assigned_by=request.user).exclude(assigned_to=request.user)
        counterparty_label = 'Assigned To'
        report_kind = 'assigned_manager'
        subtitle = 'Department assignment history, including tasks that were later deleted.'
    else:
        records = TaskReportRecord.objects.filter(assigned_to=request.user).exclude(assigned_by=request.user)
        counterparty_label = 'Assigned By'
        report_kind = 'assigned_staff'
        subtitle = 'Tasks assigned to you, including tasks that were later deleted.'

    records, filters = filter_task_report_records(records, request)

    return render(request, 'reports/task_history_report.html', {
        'report_title': 'Assigned Task Report',
        'report_subtitle': subtitle,
        'records': records,
        'filters': filters,
        'counterparty_label': counterparty_label,
        'report_kind': report_kind,
        'show_counterparty': True,
    })

@login_required
def reassign_task(request, task_id):
    task = Task.objects.get(id=task_id)

    if request.user.role != 'manager':
        return redirect('assigned_tasks')

    if request.method == 'POST':
        new_user_id = request.POST.get('assigned_to')
        new_user = User.objects.get(id=new_user_id)

        # Find existing usertask for this task
        existing_usertask = UserTask.objects.filter(task=task, assigned_to__in=[new_user, request.user]).first()

        if existing_usertask:
            # Update existing usertask
            existing_usertask.assigned_to = new_user
            existing_usertask.assigned_by = request.user
            existing_usertask.status = 'pending'
            existing_usertask.review_status = 'pending'
            existing_usertask.save()
            sync_task_report_records(usertasks=[existing_usertask])
        else:
            # Create new assignment
            usertask = UserTask.objects.create(
                task=task,
                assigned_by=request.user,
                assigned_to=new_user,
                status='pending',
                review_status='pending'
            )
            sync_task_report_records(usertasks=[usertask])

        create_notification(
            user=new_user,
            title='Task reassigned to you',
            message=f'A task has been assigned to you: {task.title}.',
            notification_type='task_assigned',
            task=task,
            target_url=reverse('task_detail', args=[task.id]),
        )

        return redirect('assigned_tasks')

    # GET request: show manager a dropdown to select user
    staff_users = User.objects.filter(role='staff')
    return render(request, 'tasks/reassign_task.html', {
        'task': task,
        'staff_users': staff_users
    })

# #dashboard view
# @login_required
# def dashboard(request):
#     user = request.user
#     today = timezone.localdate()  # Tanzanian date if timezone set

#     if user.role == "manager":
#         # Tasks assigned to staff in this manager's section
#         section_staff_tasks = UserTask.objects.filter(
#             assigned_to__role='staff',
#             assigned_to__section=user.section
#         )

#         my_open_tasks_count = section_staff_tasks.exclude(status__in=['completed', 'rejected']).count()
#         overdue_tasks_count = section_staff_tasks.filter(
#             task__due_date__lt=today
#         ).exclude(status__in=['completed', 'rejected']).count()

#         rejected_tasks_count = UserTask.objects.filter(
#             assigned_by=request.user,
#             review_status='rejected'
#         ).count()

#         completed_tasks_count = section_staff_tasks.filter(status='completed').count()

#     else:
#         # Staff sees only their own tasks
#         my_open_tasks_count = UserTask.objects.filter(
#             assigned_to=user
#         ).exclude(status__in=['completed', 'rejected']).count()

#         overdue_tasks_count = UserTask.objects.filter(
#             assigned_to=user,
#             task__due_date__lt=today
#         ).exclude(status__in=['completed', 'rejected']).count()

#         rejected_tasks_count = UserTask.objects.filter(
#         assigned_to=request.user,
#         review_status='rejected'
#          ).count()

#         completed_tasks_count = UserTask.objects.filter(
#             assigned_to=user,
#             status='completed'
#         ).count()

#     return render(request, "tasks/dashboard.html", {
#         'my_open_tasks_count': my_open_tasks_count,
#         'overdue_tasks_count': overdue_tasks_count,
#         'rejected_tasks_count': rejected_tasks_count,
#         'completed_tasks_count': completed_tasks_count,
#     })


@login_required
def do_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user_task = get_object_or_404(UserTask, task=task, assigned_to=request.user)

    if request.user.role == 'manager':
        return HttpResponseForbidden("Managers should use task_detail or review_task.")

    # Only allow assigned staff to "do" the task
    if not user_task:
        return HttpResponseForbidden("You are not assigned to this task.")

    is_assigned_task = user_task.assigned_by != request.user
    task_completed = user_task.status == 'completed'

    subtasks = task.subtasks.all()
    incomplete_subtasks = subtasks.exclude(status='completed').exists()

    context = {
        'task': task,
        'user_task': user_task,
        'is_assigned_task': is_assigned_task,
        'task_completed': task_completed,
        'subtasks': subtasks,
        'incomplete_subtasks': incomplete_subtasks,
        'can_complete': not incomplete_subtasks and not task_completed,
        # Add more action-related flags if needed
    }

    return render(request, 'tasks/do_task.html', context)

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date
import pytz

from .models import Task, UserTask, SubTask, Comment, TaskAttachment


@login_required
def task_detail(request, task_id):
    """
    Detailed view of a single task.
    Works for:
    - Manager viewing any task they assigned (or their own)
    - Staff viewing tasks assigned to them
    """
    task = get_object_or_404(Task, id=task_id)

    # Tanzanian timezone consistency (same as your other views)
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    # ───────────────────────────────────────────────
    # Permission check + context determination
    # ───────────────────────────────────────────────
    can_view = False
    is_manager_view = request.user.role == 'manager'
    is_my_own_task = False
    is_assigned_task = False
    own_usertask = None
    can_delete = False
    can_edit = False

    # All UserTask records related to this task
    all_usertasks = UserTask.objects.filter(task=task).select_related('assigned_to', 'assigned_by')

    # Check if current user has any relationship to the task
    user_related_ut = all_usertasks.filter(
        Q(assigned_to=request.user) | Q(assigned_by=request.user)
    ).first()
    
    if user_related_ut:
        can_view = True

        # ── Determine type of relationship ──
        if user_related_ut.assigned_by == request.user and user_related_ut.assigned_to == request.user:
            is_my_own_task = True

        if user_related_ut.assigned_to == request.user and user_related_ut.assigned_by != request.user:
            is_assigned_task = True
            own_usertask = user_related_ut

    # Managers can view any task they ever assigned (even if not current assignee)
    if is_manager_view and all_usertasks.filter(assigned_by=request.user).exists():
        can_view = True

    if not can_view:
        return HttpResponseForbidden("You do not have permission to view this task.")

    # ───────────────────────────────────────────────
    # Manager-specific permissions
    # ───────────────────────────────────────────────
    if is_manager_view:
        can_delete = all_usertasks.filter(assigned_by=request.user).exists()
        can_edit = can_delete  # usually same condition

    # ───────────────────────────────────────────────
    # Compute task-level status (same logic as assigned_tasks)
    # ───────────────────────────────────────────────
    computed_status = 'pending'
    if all_usertasks.exists():
        statuses = {ut.status for ut in all_usertasks}
        if statuses == {'completed'}:
            computed_status = 'completed'
        elif statuses == {'rejected'}:
            computed_status = 'rejected'
        elif 'in_progress' in statuses:
            computed_status = 'in_progress'
        elif 'completed' in statuses:
            computed_status = 'partially_completed'  # optional - you can customize

    # ───────────────────────────────────────────────
    # Days left / overdue calculation
    # ───────────────────────────────────────────────
    days_left = (task.due_date - today).days
    is_overdue = days_left < 0 and computed_status in ['pending', 'in_progress']

    # ───────────────────────────────────────────────
    # Subtasks
    # ───────────────────────────────────────────────
    subtasks = task.subtasks.select_related('created_by').all()
    incomplete_subtasks_exist = subtasks.exclude(status='completed').exists()

    # ───────────────────────────────────────────────
    # Attachments (both main task attachment + extras)
    # ───────────────────────────────────────────────
    main_attachment = task.attachment
    extra_attachments = TaskAttachment.objects.filter(task=task).select_related('uploaded_by')

    # ───────────────────────────────────────────────
    # Comments (all – including replies)
    # ───────────────────────────────────────────────
    comments = Comment.objects.filter(
        task=task,
        parent__isnull=True
    ).select_related('user').prefetch_related('replies__user').order_by('-created_at')

    # ───────────────────────────────────────────────
    # Assigned people (clean list – exclude duplicates)
    # ───────────────────────────────────────────────
    assigned_users = all_usertasks.values(
        'assigned_to__id',
        'assigned_to__email',
        'status',
        'review_status'
    ).distinct()
    # Determine correct completion status

    manager_own_ut = all_usertasks.filter(
        assigned_by=request.user,
        assigned_to=request.user
    ).first()

    if own_usertask:
        task_completed = own_usertask.status == 'completed'
    elif manager_own_ut:
        task_completed = manager_own_ut.status == 'completed'
    else:
        task_completed = computed_status == 'completed'

    can_complete = (
    not task_completed and (is_assigned_task or is_my_own_task)
    )
    
    context = {
        'task': task,
        'all_usertasks': all_usertasks,
        'own_usertask': own_usertask,
        'computed_status': computed_status,
        'is_my_task': is_my_own_task,
        'is_assigned_task': is_assigned_task,
        'task_completed': own_usertask.status == 'completed' if own_usertask else False,
        'task_reviewed': own_usertask.review_status in ['accepted', 'rejected'] if own_usertask else False,
        'can_delete': can_delete,
        'can_edit': can_edit,
        'days_left': max(days_left, 0),
        'is_overdue': is_overdue,
        'subtasks': subtasks,
        'incomplete_subtasks': incomplete_subtasks_exist,
        'main_attachment': main_attachment,
        'extra_attachments': extra_attachments,
        'comments': comments,
        'assigned_users': assigned_users,
        'today': today,
        'can_complete': can_complete,
    }

    return render(request, 'tasks/task_detail.html', context)


#get subtask for populating the modal
@login_required
def subtask_json(request, subtask_id):
    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    return JsonResponse({
        'id': subtask.id,
        'title': subtask.title,
        'description': subtask.description,
    })




#start a task
@login_required
def start_task(request, usertask_id):
    ut = get_object_or_404(UserTask, id=usertask_id, assigned_to=request.user)
    ut.status = 'in_progress'
    ut.review_status = 'pending'   # reset review status
    ut.save()
    sync_task_report_records(usertasks=[ut])

    # Conditional redirect
    if ut.assigned_to == ut.assigned_by:
        return redirect('my_tasks')          # my own task
    else:
        return redirect('assigned_tasks')    # task assigned by someone else


#complete a subtask
@login_required
def complete_subtask(request, subtask_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    subtask.status = 'completed'
    subtask.save()

    return JsonResponse({'success': True})



#complete tasks*validate subtasks)
@login_required
def complete_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    task = get_object_or_404(Task, id=task_id)

    user_task = get_object_or_404(
        UserTask,
        task=task,
        assigned_to=request.user
    )

    # ❗ Validate subtasks first
    if task.subtasks.exclude(status='completed').exists():
        return JsonResponse(
            {'error': 'Complete all subtasks first.'},
            status=400
        )

    is_assigned_task = (
        user_task.assigned_to == request.user and
        user_task.assigned_by != request.user
    )

    # ✅ Handle attachments ONLY for assigned tasks
    if is_assigned_task:
        files = request.FILES.getlist('attachments')

        if len(files) > 3:
            return JsonResponse({'error': 'Maximum 3 attachments allowed.'}, status=400)

        for f in files:
            TaskAttachment.objects.create(
                task=task,
                uploaded_by=request.user,
                file=f
            )

    # For manager-assigned tasks, completing once should reflect as completed
    # for both the assigned staff view and the manager view.
    if is_assigned_task:
        UserTask.objects.filter(task=task).update(
            status='completed',
            completed_at=timezone.now()
        )
        sync_task_report_records(task=task)
    else:
        user_task.status = 'completed'
        user_task.completed_at = timezone.now()
        user_task.save(update_fields=['status', 'completed_at'])
        sync_task_report_records(usertasks=[user_task])

    task.completed_by = request.user
    task.completed_at = timezone.now()
    task.save()

    if is_assigned_task and user_task.assigned_by:
        create_notification(
            user=user_task.assigned_by,
            title='Task ready for review',
            message=f'{request.user.email} completed "{task.title}" and it is ready for review.',
            notification_type='task_review',
            task=task,
            target_url=reverse('review_task', args=[task.id]),
        )

    return JsonResponse({'success': True})




#delete a task
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return HttpResponseForbidden("You cannot delete this task.")

    snapshot_rows = list(task.user_tasks.select_related('assigned_by', 'assigned_to', 'task', 'task__category'))
    sync_task_report_records(usertasks=snapshot_rows, mark_deleted=True)
    task.delete()
    messages.success(request, "Task deleted successfully.")
    return redirect('my_tasks')



#edit task
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Task, UserTask, User, CategoryMember


@login_required
def edit_task(request, id):
    task = get_object_or_404(Task, id=id)
    usertasks = task.user_tasks.select_related('assigned_to', 'assigned_by')

    is_my_task = usertasks.filter(
        assigned_by=request.user,
        assigned_to=request.user
    ).exists()
    is_assigned_task = usertasks.filter(
        assigned_by=request.user
    ).exclude(
        assigned_to=request.user
    ).exists()

    if not (is_my_task or is_assigned_task):
        return HttpResponseForbidden("You cannot edit this task.")

    categories = Category.objects.none()
    assigned_staff_ids = []
    selected_category_id = task.category_id

    if is_assigned_task:
        categories = Category.objects.filter(section=request.user.section)
        assigned_staff_ids = list(
            usertasks.exclude(assigned_to=request.user).values_list('assigned_to_id', flat=True)
        )

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        due_date = request.POST.get("due_date")
        priority = request.POST.get("priority", "normal")
        attachment = request.FILES.get("attachment")

        if not title or not due_date:
            return JsonResponse({"error": "Title and due date are required."}, status=400)

        task.title = title
        task.description = description
        task.due_date = due_date
        task.priority = priority

        if attachment:
            task.attachment = attachment

        redirect_url = reverse("my_tasks")

        if is_assigned_task:
            category_id = request.POST.get("category_id")
            selected_user_ids = request.POST.getlist("assigned_to[]")

            category = Category.objects.filter(
                id=category_id,
                section=request.user.section
            ).first()

            if not category:
                return JsonResponse({"error": "Please select a valid category."}, status=400)

            selected_users = list(
                User.objects.filter(
                    id__in=selected_user_ids,
                    role='staff',
                    section=request.user.section,
                    is_active=True,
                    categorymember__category=category
                ).distinct()
            )

            if not selected_users:
                return JsonResponse({"error": "Select at least one staff member."}, status=400)

            task.category = category
            redirect_url = reverse("assigned_tasks")
        else:
            task.category = None
            selected_users = [request.user]

        task.save()

        existing_usertasks = {
            ut.assigned_to_id: ut for ut in task.user_tasks.all()
        }
        selected_ids = {selected_user.id for selected_user in selected_users}

        for assignee in selected_users:
            if assignee.id in existing_usertasks:
                ut = existing_usertasks[assignee.id]
                if is_assigned_task:
                    ut.assigned_by = request.user
                ut.save(update_fields=['assigned_by'])
                sync_task_report_records(usertasks=[ut])
            else:
                ut = UserTask.objects.create(
                    task=task,
                    assigned_by=request.user,
                    assigned_to=assignee,
                    status='pending',
                    review_status='pending'
                )
                sync_task_report_records(usertasks=[ut])
                if is_assigned_task:
                    create_notification(
                        user=assignee,
                        title='Task updated',
                        message=f'Task details were updated: {task.title}.',
                        notification_type='task_assigned',
                        task=task,
                        target_url=reverse('task_detail', args=[task.id]),
                    )

        removed_usertasks = list(
            task.user_tasks.select_related('assigned_by', 'assigned_to', 'task', 'task__category')
            .exclude(assigned_to_id__in=selected_ids)
        )
        if removed_usertasks:
            sync_task_report_records(usertasks=removed_usertasks, mark_deleted=True)
        task.user_tasks.exclude(assigned_to_id__in=selected_ids).delete()
        sync_task_report_records(task=task)

        return JsonResponse({
            "message": "Task updated successfully!",
            "redirect_url": redirect_url
        })

    context = {
        "task": task,
        "categories": categories,
        "assigned_staff_ids": assigned_staff_ids,
        "selected_category_id": selected_category_id,
        "PRIORITY_CHOICES": Task.PRIORITY_CHOICES,
        "is_my_task": is_my_task,
        "is_assigned_task": is_assigned_task,
    }
    return render(request, "tasks/edit_task.html", context)

from django.views.decorators.http import require_GET, require_POST

@require_GET
def get_staff_by_category(request):
    category_id = request.GET.get("category_id")
    if not category_id:
        return JsonResponse({"staff": []})
    
    # Filter staff who belong to this category
    staff = User.objects.filter(category__id=category_id).values("id", "email")
    staff_list = list(staff)
    return JsonResponse({"staff": staff_list})

#edit subtask
@login_required
def ajax_save_subtask(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask_id = request.POST.get('id')
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '')

    if not subtask_id and task.user_tasks.filter(status='completed').exists():
        return JsonResponse({'error': 'This task is already completed. You cannot add another subtask.'}, status=400)

    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    if subtask_id:
        subtask = get_object_or_404(SubTask, id=subtask_id)

        if subtask.created_by != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)

        subtask.title = title
        subtask.description = description
        subtask.save()
    else:
        SubTask.objects.create(
            task=task,
            title=title,
            description=description,
            created_by=request.user
        )

    return JsonResponse({'success': True})



#delete subtask
@login_required
def delete_subtask(request, subtask_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)

    subtask = get_object_or_404(SubTask, id=subtask_id)

    if subtask.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    subtask.delete()
    return JsonResponse({'success': True})




#review task
@login_required
def review_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # 🔐 Only the manager who assigned the task can review it
    if not UserTask.objects.filter(task=task, assigned_by=request.user).exists():
        return HttpResponseForbidden("You cannot review this task.")

    # Assigned staff (exclude manager)
    assigned_staff = (
        User.objects
        .filter(tasks_received__task=task)
        .exclude(id=request.user.id)
        .distinct()
    )

    # Attachments uploaded for this task
    attachments = task.attachments.all()

    # Fetch all major comments for this task (parent is None)
    major_comments = Comment.objects.filter(task=task, parent=None).order_by('-created_at')
    # Each major comment can access its replies via `comment.replies.all()`

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()

        if action == 'reject' and not reason:
            messages.error(request, "Rejection reason is required.")
            return redirect('review_task', task_id=task.id)

        elif action == 'accept':
            # UserTask.objects.filter(task=task, assigned_by=request.user).update(status='accepted')
            UserTask.objects.filter(task=task).update(review_status='accepted')
            sync_task_report_records(task=task)
            messages.success(request, "Task accepted successfully.")

        elif action == 'reject':
            UserTask.objects.filter(task=task, assigned_by=request.user).update(review_status='rejected', status='pending')
            sync_task_report_records(task=task)
            Comment.objects.create(
                user=request.user,
                task=task,
                comment=reason
            )
            messages.success(request, "Task rejected with reason.")

        return redirect('assigned_tasks')

    return render(request, 'tasks/review_task.html', {
        'task': task,
        'assigned_staff': assigned_staff,
        'attachments': attachments,
        'major_comments': major_comments,
    })


@login_required
def notification_redirect(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if notification.target_url:
        return redirect(notification.target_url)

    return redirect('assigned_tasks')


@login_required
@require_POST
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER', 'assigned_tasks'))



#reply to a comment
@login_required
def reply_comment(request, comment_id):
    parent_comment = get_object_or_404(Comment, id=comment_id)
    task = parent_comment.task

    # 🚫 Prevent replying to your own comment
    if parent_comment.user == request.user:
        return HttpResponseForbidden("You cannot reply to your own comment.")

    # Find task relationship
    user_task = UserTask.objects.filter(task=task).first()

    if not user_task:
        return HttpResponseForbidden("Task assignment not found.")

    is_staff = user_task.assigned_to == request.user
    is_manager = user_task.assigned_by == request.user

    # Only assigned staff or assigning manager can reply
    if not (is_staff or is_manager):
        return HttpResponseForbidden("You cannot reply on this task.")

    if request.method == 'POST':
        reply_text = request.POST.get('comment')
        if reply_text:
            Comment.objects.create(
                user=request.user,
                task=task,
                parent=parent_comment,
                comment=reply_text
            )

    # 🔁 Redirect based on role
    if is_manager:
        return redirect('review_task', task_id=task.id)

    return redirect('task_detail', task_id=task.id)




@login_required
@require_POST
def delete_task_cascade(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # Only managers can delete tasks they assigned
    if request.user.role != 'manager':
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if not UserTask.objects.filter(
        task=task,
        assigned_by=request.user
    ).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)

    snapshot_rows = list(task.user_tasks.select_related('assigned_by', 'assigned_to', 'task', 'task__category'))
    sync_task_report_records(usertasks=snapshot_rows, mark_deleted=True)
    task.delete()  # CASCADE deletes all UserTask rows
    return JsonResponse({'success': True})

@login_required
def overdue_tasks_report(request):
    if request.user.role != 'manager':
        return HttpResponseForbidden()

    import pytz
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    overdue_tasks = UserTask.objects.select_related('task', 'assigned_to').filter(
        task__due_date__lt=today,
        assigned_to__role='staff',
        assigned_to__section=request.user.section
    ).exclude(status__in=['completed', 'rejected'])

    return render(request, 'reports/overdue_tasks.html', {'overdue_tasks': overdue_tasks})

@login_required
def due_soon_report(request):
    if request.user.role != 'manager':
        return HttpResponseForbidden()

    import pytz
    from datetime import timedelta
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    days_ahead = 7
    due_date_limit = today + timedelta(days=days_ahead)

    tasks = UserTask.objects.select_related('task', 'assigned_to').filter(
        task__due_date__gte=today,
        task__due_date__lte=due_date_limit,
        assigned_to__role='staff',
        assigned_to__section=request.user.section
    ).exclude(status__in=['completed', 'rejected']).order_by('task__due_date')

    due_soon_tasks = []
    for ut in tasks:
        days_left = (ut.task.due_date - today).days
        due_soon_tasks.append({'user_task': ut, 'days_left': days_left})

    return render(request, 'reports/due_soon_tasks.html', {'due_soon_tasks': due_soon_tasks})


@login_required
def staff_performance_report(request):
    tanzania_tz = pytz.timezone('Africa/Dar_es_Salaam')
    today = timezone.now().astimezone(tanzania_tz).date()

    created_from = request.GET.get('created_from', '').strip()
    created_to = request.GET.get('created_to', '').strip()
    task_source = request.GET.get('task_source', 'all').strip() or 'all'
    section_filter = request.GET.get('section', '').strip()

    if task_source not in ['all', 'manager', 'self']:
        task_source = 'all'

    if request.user.is_superuser:
        staff_users = User.objects.filter(role='staff')
        if section_filter:
            staff_users = staff_users.filter(section=section_filter)
    elif request.user.role == 'staff':
        section_filter = request.user.section
        staff_users = User.objects.filter(
            role='staff',
            section=request.user.section
        )
    else:
        section_filter = request.user.section
        staff_users = User.objects.filter(
            role='staff',
            section=request.user.section
        )

    staff_users = staff_users.order_by('username')

    def apply_date_filters(queryset):
        if created_from:
            queryset = queryset.filter(task__created_at__date__gte=created_from)
        if created_to:
            queryset = queryset.filter(task__created_at__date__lte=created_to)
        return queryset

    def summarize_tasks(queryset):
        total = queryset.count()
        completed_qs = queryset.filter(status='completed')
        completed = completed_qs.count()
        pending = queryset.filter(status__in=['pending', 'in_progress', 'accepted']).count()
        overdue = queryset.filter(task__due_date__lt=today).exclude(
            status__in=['completed', 'rejected']
        ).count()
        on_time_completed = completed_qs.filter(
            completed_at__isnull=False,
            completed_at__date__lte=F('task__due_date')
        ).count()
        late_completed = completed_qs.filter(
            completed_at__isnull=False,
            completed_at__date__gt=F('task__due_date')
        ).count()
        rejected = queryset.filter(review_status='rejected').count()
        completion_rate = round((completed / total * 100), 1) if total else 0
        on_time_rate = round((on_time_completed / completed * 100), 1) if completed else 0

        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'overdue': overdue,
            'on_time_completed': on_time_completed,
            'late_completed': late_completed,
            'rejected': rejected,
            'completion_rate': completion_rate,
            'on_time_rate': on_time_rate,
        }

    performance_data = []

    for staff in staff_users:
        manager_tasks = UserTask.objects.filter(
            assigned_to=staff
        ).select_related('task', 'assigned_by')
        if request.user.is_superuser:
            manager_tasks = manager_tasks.exclude(assigned_by=staff)
        elif request.user.role == 'staff':
            manager_tasks = manager_tasks.exclude(assigned_by=staff)
        else:
            manager_tasks = manager_tasks.filter(assigned_by=request.user)
        manager_tasks = apply_date_filters(manager_tasks)

        staff_tasks = UserTask.objects.filter(
            assigned_to=staff,
            assigned_by=staff
        ).select_related('task')
        staff_tasks = apply_date_filters(staff_tasks)

        manager_stats = summarize_tasks(manager_tasks)
        staff_stats = summarize_tasks(staff_tasks)

        if task_source == 'manager':
            combined_total = manager_stats['total']
            combined_completed = manager_stats['completed']
            combined_pending = manager_stats['pending']
            combined_overdue = manager_stats['overdue']
            combined_on_time = manager_stats['on_time_completed']
            combined_late = manager_stats['late_completed']
            combined_rejected = manager_stats['rejected']
        elif task_source == 'self':
            combined_total = staff_stats['total']
            combined_completed = staff_stats['completed']
            combined_pending = staff_stats['pending']
            combined_overdue = staff_stats['overdue']
            combined_on_time = staff_stats['on_time_completed']
            combined_late = staff_stats['late_completed']
            combined_rejected = staff_stats['rejected']
        else:
            combined_total = manager_stats['total'] + staff_stats['total']
            combined_completed = manager_stats['completed'] + staff_stats['completed']
            combined_pending = manager_stats['pending'] + staff_stats['pending']
            combined_overdue = manager_stats['overdue'] + staff_stats['overdue']
            combined_on_time = manager_stats['on_time_completed'] + staff_stats['on_time_completed']
            combined_late = manager_stats['late_completed'] + staff_stats['late_completed']
            combined_rejected = manager_stats['rejected'] + staff_stats['rejected']

        completion_rate = round((combined_completed / combined_total * 100), 1) if combined_total else 0
        on_time_rate = round((combined_on_time / combined_completed * 100), 1) if combined_completed else 0

        performance_data.append({
            'staff': staff,
            'total_tasks': combined_total,
            'completed_tasks': combined_completed,
            'pending_tasks': combined_pending,
            'overdue_tasks': combined_overdue,
            'on_time_completed': combined_on_time,
            'late_completed': combined_late,
            'rejected_tasks': combined_rejected,
            'completion_rate': completion_rate,
            'on_time_rate': on_time_rate,
            'm_total': manager_stats['total'],
            'm_completed': manager_stats['completed'],
            'm_pending': manager_stats['pending'],
            'm_overdue': manager_stats['overdue'],
            'm_on_time': manager_stats['on_time_completed'],
            'm_late': manager_stats['late_completed'],
            'm_rejected': manager_stats['rejected'],
            'm_rate': manager_stats['completion_rate'],
            'm_on_time_rate': manager_stats['on_time_rate'],
            's_total': staff_stats['total'],
            's_completed': staff_stats['completed'],
            's_pending': staff_stats['pending'],
            's_overdue': staff_stats['overdue'],
            's_on_time': staff_stats['on_time_completed'],
            's_late': staff_stats['late_completed'],
            's_rejected': staff_stats['rejected'],
            's_rate': staff_stats['completion_rate'],
            's_on_time_rate': staff_stats['on_time_rate'],
            'manager_tasks': manager_tasks,
            'staff_tasks': staff_tasks,
        })

    performance_data.sort(
        key=lambda item: (
            item['completion_rate'],
            item['on_time_rate'],
            item['completed_tasks'],
            -item['overdue_tasks']
        ),
        reverse=True
    )

    summary = {
        'staff_count': len(performance_data),
        'total_tasks': sum(item['total_tasks'] for item in performance_data),
        'completed_tasks': sum(item['completed_tasks'] for item in performance_data),
        'pending_tasks': sum(item['pending_tasks'] for item in performance_data),
        'overdue_tasks': sum(item['overdue_tasks'] for item in performance_data),
        'on_time_completed': sum(item['on_time_completed'] for item in performance_data),
        'late_completed': sum(item['late_completed'] for item in performance_data),
        'rejected_tasks': sum(item['rejected_tasks'] for item in performance_data),
    }
    summary['completion_rate'] = round(
        (summary['completed_tasks'] / summary['total_tasks'] * 100), 1
    ) if summary['total_tasks'] else 0
    summary['on_time_rate'] = round(
        (summary['on_time_completed'] / summary['completed_tasks'] * 100), 1
    ) if summary['completed_tasks'] else 0

    return render(request, 'reports/staff_performance.html', {
        'performance_data': performance_data,
        'summary': summary,
        'filters': {
            'created_from': created_from,
            'created_to': created_to,
            'task_source': task_source,
            'section': section_filter,
        },
        'section_choices': User.SECTION_CHOICES,
    })

@login_required
def staff_detail(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff')

    if request.user.is_superuser:
        all_tasks = UserTask.objects.filter(assigned_to=staff).select_related('task', 'assigned_by')
        manager_tasks = all_tasks.filter(assigned_by=request.user)
        manager_tasks_heading = "Tasks Assigned By You"
    elif request.user.role == 'manager':
        if staff.section != request.user.section:
            return HttpResponseForbidden()
        all_tasks = UserTask.objects.filter(assigned_to=staff).select_related('task', 'assigned_by')
        manager_tasks = all_tasks.filter(assigned_by=request.user)
        manager_tasks_heading = "Tasks Assigned By You"
    elif request.user.role == 'staff':
        if staff.section != request.user.section:
            return HttpResponseForbidden()
        all_tasks = UserTask.objects.filter(assigned_to=staff).select_related('task', 'assigned_by')
        manager_tasks = all_tasks.exclude(assigned_by=staff)
        manager_tasks_heading = "Tasks Assigned By Manager"
    else:
        return HttpResponseForbidden()

    context = {
        'staff': staff,
        'all_tasks': all_tasks,
        'manager_tasks': manager_tasks,
        'manager_tasks_heading': manager_tasks_heading,
    }

    return render(request, 'reports/staff_detail.html', context)

@login_required
def manager_task_detail(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff', section=request.user.section)

    if request.user.is_superuser:
        tasks = UserTask.objects.filter(assigned_to=staff).exclude(assigned_by=staff).select_related('task', 'assigned_by')
    elif request.user.role == 'manager':
        tasks = UserTask.objects.filter(assigned_by=request.user, assigned_to=staff).select_related('task', 'assigned_by')
    elif request.user.role == 'staff':
        if request.user.section != staff.section:
            return HttpResponseForbidden()
        tasks = UserTask.objects.filter(assigned_to=staff).exclude(assigned_by=staff).select_related('task', 'assigned_by')
    else:
        return HttpResponseForbidden()

    return render(request, 'reports/manager_task_detail.html', {
        'staff': staff,
        'tasks': tasks,
    })

from django.http import JsonResponse
from tasks.models import CategoryMember

def category_users_json(request):
    category_id = request.GET.get('category_id')

    users = []

    if category_id:
        members = CategoryMember.objects.filter(
            category_id=category_id
        ).select_related('user')

        users = [
            {
                'id': m.user.id,
                                'name': m.user.username
            }
            for m in members
        ]

    return JsonResponse({'users': users})

@login_required
def staff_task_detail(request, staff_id):

    # if request.user.role != 'manager':
    #     return HttpResponseForbidden()

    # Ensure the staff is in the same section
    staff = get_object_or_404(User, id=staff_id, role='staff', section=request.user.section)

    # Only tasks assigned TO this staff AND assigned BY the same staff (self-assigned)
    tasks = UserTask.objects.filter(
        assigned_to=staff,
        assigned_by=staff
    ).select_related('task')

    return render(request, 'reports/staff_task_detail.html', {
        'staff': staff,
        'tasks': tasks,
    })
