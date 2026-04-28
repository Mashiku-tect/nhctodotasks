import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import Task, UserTask, SubTask, Comment, TaskAttachment, Category, Notification, TaskReportRecord, DailyCheckIn
from .notifications import create_notification
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


def build_task_attachment_list(task):
    attachments = []

    if task.attachment:
        attachments.append({
            'name': os.path.basename(task.attachment.name),
            'url': task.attachment.url,
            'uploaded_by': None,
            'created_at': task.created_at,
            'is_legacy': True,
        })

    for attachment in task.attachments.select_related('uploaded_by').all():
        attachments.append({
            'name': os.path.basename(attachment.file.name),
            'url': attachment.file.url,
            'uploaded_by': attachment.uploaded_by,
            'created_at': attachment.created_at,
            'is_legacy': False,
        })

    attachments.sort(key=lambda item: item['created_at'] or timezone.now())
    return attachments


def create_task_attachments(task, files, uploaded_by):
    for uploaded_file in files:
        TaskAttachment.objects.create(
            task=task,
            uploaded_by=uploaded_by,
            file=uploaded_file,
        )

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
        attachments = request.FILES.getlist("attachments")
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
            category=category
        )
        create_task_attachments(task, attachments, user)

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
        task.countdown_stopped = ut.status == 'completed'
        task.days_left = None if task.countdown_stopped or not task.due_date else (task.due_date - today).days
        task.attachment_files = build_task_attachment_list(task)
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

        is_review_accepted = False
        if user.role == 'manager':
            is_review_accepted = display_usertasks.exists() and all(
                ut.review_status == 'accepted' for ut in display_usertasks
            )
        elif own_usertask:
            is_review_accepted = (
                own_usertask.status == 'completed' and own_usertask.review_status == 'accepted'
            )

        countdown_stopped = is_review_accepted
        days_left = None if countdown_stopped else (task.due_date - today).days
        is_overdue = days_left is not None and days_left < 0 and computed_status in ['pending', 'in_progress']
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
            "countdown_stopped": countdown_stopped,
            "is_overdue": is_overdue,
            "reassign_needed": reassign_needed,
            "deadline_progress": deadline_progress,
            "completed_by": task.completed_by,
            "attachment_files": build_task_attachment_list(task),
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


def get_local_today():
    return timezone.now().astimezone(tanzania_tz).date()


@login_required
def daily_accountability_board(request):
    if request.user.is_superuser:
        return redirect('daily_digest')

    today = get_local_today()
    active_tasks = UserTask.objects.filter(
        assigned_to=request.user
    ).exclude(
        status__in=['completed', 'accepted', 'rejected']
    ).filter(
        task__due_date__gte=today
    ).select_related('task', 'assigned_by').order_by('task__due_date', '-task__priority', '-created_at')

    completed_today = UserTask.objects.filter(
        assigned_to=request.user,
        completed_at__date=today
    ).select_related('task').order_by('-completed_at')

    checkin, _ = DailyCheckIn.objects.get_or_create(
        user=request.user,
        entry_date=today,
    )

    if request.method == 'POST':
        selected_task_ids = [
            int(task_id)
            for task_id in request.POST.getlist('priority_task_ids')
            if task_id.isdigit()
        ]

        allowed_task_ids = set(active_tasks.values_list('id', flat=True))
        valid_selected_ids = [task_id for task_id in selected_task_ids if task_id in allowed_task_ids]

        checkin.morning_focus = request.POST.get('morning_focus', '').strip()
        checkin.progress_update = request.POST.get('progress_update', '').strip()
        checkin.end_of_day_summary = request.POST.get('end_of_day_summary', '').strip()
        checkin.tomorrow_plan = request.POST.get('tomorrow_plan', '').strip()
        checkin.blockers = request.POST.get('blockers', '').strip()

        uploaded_file = request.FILES.get('proof_file')
        if uploaded_file:
            checkin.proof_file = uploaded_file

        action = request.POST.get('action')
        if action == 'submit':
            has_meaningful_content = any([
                valid_selected_ids,
                checkin.morning_focus,
                checkin.progress_update,
                checkin.end_of_day_summary,
                checkin.tomorrow_plan,
                checkin.blockers,
                uploaded_file or checkin.proof_file,
            ])

            if not has_meaningful_content:
                messages.error(
                    request,
                    'Add at least one update, priority task, blocker, summary, plan, or proof before submitting.'
                )
                return redirect('daily_board')

            checkin.is_submitted = True
            checkin.submitted_at = timezone.now()

        checkin.save()
        checkin.priority_tasks.set(valid_selected_ids)

        if action == 'submit':
            managers = User.objects.filter(
                role='manager',
                section=request.user.section,
                is_active=True
            )
            target_url = reverse('daily_digest')
            for manager in managers:
                create_notification(
                    user=manager,
                    title='Daily check-in submitted',
                    message=f'{request.user.username} submitted today\'s accountability update.',
                    notification_type='task_updated',
                    target_url=target_url,
                )
            messages.success(request, 'Daily accountability update submitted successfully.')
        else:
            messages.success(request, 'Daily accountability draft saved.')

        return redirect('daily_board')

    selected_priority_ids = set(checkin.priority_tasks.values_list('id', flat=True))

    return render(request, 'tasks/daily_board.html', {
        'today': today,
        'open_tasks': active_tasks,
        'completed_today': completed_today,
        'checkin': checkin,
        'selected_priority_ids': selected_priority_ids,
    })


@login_required
def daily_digest(request):
    today = get_local_today()
    section_filter = request.GET.get('section', '').strip()

    if request.user.is_superuser:
        staff_qs = User.objects.filter(role='staff', is_active=True)
        if section_filter:
            staff_qs = staff_qs.filter(section=section_filter)
    elif request.user.role == 'manager':
        section_filter = request.user.section
        staff_qs = User.objects.filter(
            role='staff',
            section=request.user.section,
            is_active=True
        )
    else:
        return redirect('daily_board')

    checkins = {
        checkin.user_id: checkin
        for checkin in DailyCheckIn.objects.filter(
            user__in=staff_qs,
            entry_date=today
        ).prefetch_related('priority_tasks__task')
    }

    digest_rows = []
    for staff in staff_qs.order_by('username'):
        checkin = checkins.get(staff.id)
        completed_count = UserTask.objects.filter(
            assigned_to=staff,
            completed_at__date=today
        ).count()

        digest_rows.append({
            'staff': staff,
            'checkin': checkin,
            'completed_count': completed_count,
            'has_blocker': bool(checkin and checkin.blockers.strip()),
            'is_silent': checkin is None or not checkin.is_submitted,
        })

    summary = {
        'staff_count': len(digest_rows),
        'submitted_count': sum(1 for row in digest_rows if row['checkin'] and row['checkin'].is_submitted),
        'blocker_count': sum(1 for row in digest_rows if row['has_blocker']),
        'silent_count': sum(1 for row in digest_rows if row['is_silent']),
        'completed_count': sum(row['completed_count'] for row in digest_rows),
    }

    return render(request, 'reports/daily_digest.html', {
        'today': today,
        'digest_rows': digest_rows,
        'summary': summary,
        'filters': {'section': section_filter},
        'section_choices': User.SECTION_CHOICES,
    })


@login_required
def daily_checkin_detail(request, user_id):
    target_user = get_object_or_404(User, id=user_id, role='staff')
    today = get_local_today()

    if request.user.is_superuser:
        pass
    elif request.user.role == 'manager':
        if target_user.section != request.user.section:
            return HttpResponseForbidden()
    else:
        return HttpResponseForbidden()

    checkin = DailyCheckIn.objects.filter(
        user=target_user,
        entry_date=today
    ).prefetch_related('priority_tasks__task').first()

    completed_today = UserTask.objects.filter(
        assigned_to=target_user,
        completed_at__date=today
    ).select_related('task').order_by('-completed_at')

    return render(request, 'reports/daily_checkin_detail.html', {
        'today': today,
        'target_user': target_user,
        'checkin': checkin,
        'completed_today': completed_today,
    })


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
            'title': 'Performance Dashboard',
            'description': 'Track staff performance, rankings, and section productivity trends.',
            'icon': 'bi-trophy',
            'url': reverse('reports_performance'),
        },
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

    if not UserTask.objects.filter(task=task, assigned_by=request.user).exists():
        return redirect('assigned_tasks')

    categories = Category.objects.filter(section=request.user.section).order_by('name')
    selected_category_id = task.category_id
    staff_users = User.objects.none()

    if selected_category_id:
        staff_users = User.objects.filter(
            role='staff',
            section=request.user.section,
            is_active=True,
            categorymember__category_id=selected_category_id
        ).distinct().order_by('username')

    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        new_user_id = request.POST.get('assigned_to')

        category = Category.objects.filter(
            id=category_id,
            section=request.user.section
        ).first()

        if not category:
            messages.error(request, 'Please select a valid category before reassigning.')
            return render(request, 'tasks/reassign_task.html', {
                'task': task,
                'categories': categories,
                'staff_users': staff_users,
                'selected_category_id': selected_category_id,
            })

        selected_category_id = category.id
        staff_users = User.objects.filter(
            role='staff',
            section=request.user.section,
            is_active=True,
            categorymember__category=category
        ).distinct().order_by('username')

        new_user = staff_users.filter(id=new_user_id).first()
        if not new_user:
            messages.error(request, 'Please select a valid staff member from the chosen category.')
            return render(request, 'tasks/reassign_task.html', {
                'task': task,
                'categories': categories,
                'staff_users': staff_users,
                'selected_category_id': selected_category_id,
            })

        task.category = category
        task.save(update_fields=['category', 'updated_at'])
        previous_assignees = list(
            task.user_tasks.exclude(assigned_to=request.user).select_related('assigned_to')
        )

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
            message=f'{task.title} has been reassigned to you.',
            notification_type='task_reassigned',
            task=task,
            target_url=reverse('task_detail', args=[task.id]),
        )

        previous_usernames = ", ".join(
            prev.assigned_to.username for prev in previous_assignees if prev.assigned_to_id != new_user.id
        ) or 'another staff member'
        create_notification(
            user=request.user,
            title='Task reassigned',
            message=f'"{task.title}" was reassigned from {previous_usernames} to {new_user.username}.',
            notification_type='task_reassigned',
            task=task,
            target_url=reverse('task_detail', args=[task.id]),
        )

        return redirect('assigned_tasks')

    return render(request, 'tasks/reassign_task.html', {
        'task': task,
        'staff_users': staff_users,
        'categories': categories,
        'selected_category_id': selected_category_id,
    })

@login_required
def dashboard(request):
    user = request.user
    today = timezone.now().astimezone(tanzania_tz).date()

    if user.is_superuser:
        visible_tasks = UserTask.objects.select_related('task', 'assigned_to', 'assigned_by')
        active_staff_count = User.objects.filter(role='staff', is_active=True).count()
        scope_label = 'All sections overview'
        headline = 'System-wide task overview'
    elif user.role == 'manager':
        visible_tasks = UserTask.objects.filter(
            Q(assigned_by=user) | Q(assigned_to=user)
        ).select_related('task', 'assigned_to', 'assigned_by').distinct()
        active_staff_count = User.objects.filter(
            role='staff',
            section=user.section,
            is_active=True
        ).count()
        scope_label = f'{user.get_section_display()} section'
        headline = 'Overview of your section tasks'
    else:
        visible_tasks = UserTask.objects.filter(
            assigned_to=user
        ).select_related('task', 'assigned_to', 'assigned_by')
        active_staff_count = None
        scope_label = 'My work overview'
        headline = 'Overview of your tasks and updates'

    total_tasks = visible_tasks.count()
    completed_tasks = visible_tasks.filter(status='completed').count()
    in_progress_tasks = visible_tasks.filter(status='in_progress').count()
    pending_tasks = visible_tasks.filter(status='pending').count()
    overdue_tasks = visible_tasks.filter(task__due_date__lt=today).exclude(
        status__in=['completed', 'rejected', 'accepted']
    ).count()
    review_pending = visible_tasks.filter(
        status='completed',
        review_status='pending'
    ).exclude(
        assigned_by=F('assigned_to')
    ).count()

    recent_tasks = visible_tasks.order_by('-task__updated_at', '-created_at')[:6]
    recent_notifications = Notification.objects.filter(
        user=user
    ).order_by('-created_at')[:6]

    quick_links = [
        {
            'title': 'My Tasks',
            'description': 'Open your personal task list.',
            'icon': 'bi-list-task',
            'url': reverse('my_tasks'),
        },
        {
            'title': 'Assigned Tasks',
            'description': 'See tasks shared between you and others.',
            'icon': 'bi-person-check',
            'url': reverse('assigned_tasks'),
        },
        {
            'title': 'Create Task',
            'description': 'Create a new task or assignment.',
            'icon': 'bi-plus-circle',
            'url': reverse('create_task'),
        },
        {
            'title': 'Performance',
            'description': 'Open the staff performance dashboard.',
            'icon': 'bi-trophy',
            'url': reverse('reports_performance'),
        },
    ]

    if user.role == 'manager' or user.is_superuser:
        quick_links.append({
            'title': 'Daily Digest',
            'description': 'Review section check-ins and blockers.',
            'icon': 'bi-calendar2-check',
            'url': reverse('daily_digest'),
        })
    else:
        quick_links.append({
            'title': 'Daily Board',
            'description': 'Update today’s focus and progress.',
            'icon': 'bi-calendar2-check',
            'url': reverse('daily_board'),
        })

    stat_cards = [
        {
            'label': 'Total Tasks',
            'value': total_tasks,
            'meta': scope_label,
            'icon': 'bi-journal-text',
            'tone': 'cyan',
        },
        {
            'label': 'Completed',
            'value': completed_tasks,
            'meta': 'Finished work',
            'icon': 'bi-check2-square',
            'tone': 'green',
        },
        {
            'label': 'In Progress',
            'value': in_progress_tasks,
            'meta': 'Active right now',
            'icon': 'bi-hourglass-split',
            'tone': 'blue',
        },
        {
            'label': 'Pending',
            'value': pending_tasks,
            'meta': 'Waiting to start',
            'icon': 'bi-stopwatch',
            'tone': 'amber',
        },
        {
            'label': 'Overdue',
            'value': overdue_tasks,
            'meta': 'Needs attention',
            'icon': 'bi-alarm',
            'tone': 'red',
        },
    ]

    if active_staff_count is not None:
        stat_cards.append({
            'label': 'Active Staff',
            'value': active_staff_count,
            'meta': scope_label,
            'icon': 'bi-people',
            'tone': 'violet',
        })
    else:
        stat_cards.append({
            'label': 'Awaiting Review',
            'value': review_pending,
            'meta': 'Completed tasks pending feedback',
            'icon': 'bi-chat-square-text',
            'tone': 'violet',
        })

    return render(request, "tasks/dashboard.html", {
        'headline': headline,
        'scope_label': scope_label,
        'stat_cards': stat_cards,
        'recent_tasks': recent_tasks,
        'recent_notifications': recent_notifications,
        'quick_links': quick_links,
        'today': today,
    })


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
    attachment_files = build_task_attachment_list(task)

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
        'attachment_files': attachment_files,
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
        attachments = request.FILES.getlist("attachments")

        if not title or not due_date:
            return JsonResponse({"error": "Title and due date are required."}, status=400)

        task.title = title
        task.description = description
        task.due_date = due_date
        task.priority = priority

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
        create_task_attachments(task, attachments, request.user)

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
                if is_assigned_task and assignee != request.user:
                    create_notification(
                        user=assignee,
                        title='Task updated',
                        message=f'Task details were updated: {task.title}.',
                        notification_type='task_updated',
                        task=task,
                        target_url=reverse('task_detail', args=[task.id]),
                    )
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
                        title='New task assigned',
                        message=f'You have been assigned a new task: {task.title}.',
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
        "attachment_files": build_task_attachment_list(task),
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
    attachments = build_task_attachment_list(task)

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
            for user_task in task.user_tasks.select_related('assigned_to').exclude(assigned_to=request.user):
                create_notification(
                    user=user_task.assigned_to,
                    title='Task accepted',
                    message=f'Your work on "{task.title}" was accepted.',
                    notification_type='task_accepted',
                    task=task,
                    target_url=reverse('task_detail', args=[task.id]),
                )
            messages.success(request, "Task accepted successfully.")

        elif action == 'reject':
            UserTask.objects.filter(task=task, assigned_by=request.user).update(review_status='rejected', status='pending')
            sync_task_report_records(task=task)
            Comment.objects.create(
                user=request.user,
                task=task,
                comment=reason
            )
            for user_task in task.user_tasks.select_related('assigned_to').exclude(assigned_to=request.user):
                create_notification(
                    user=user_task.assigned_to,
                    title='Task rejected',
                    message=f'Your work on "{task.title}" was rejected. Reason: {reason}',
                    notification_type='task_rejected',
                    task=task,
                    target_url=reverse('task_detail', args=[task.id]),
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
def notifications_list(request):
    notifications = request.user.notifications.order_by('-created_at')
    paginator = Paginator(notifications, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'tasks/notifications.html', {
        'page_obj': page_obj,
        'notifications': page_obj,
    })


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
    section_filter = request.GET.get('section', '').strip()
    staff_type_filter = request.GET.get('staff_type', '').strip()

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

    if staff_type_filter in dict(User.STAFF_TYPE_CHOICES):
        staff_users = staff_users.filter(staff_type=staff_type_filter)

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
        eligible_for_scoring = completed + overdue + rejected
        weighted_completed_points = (on_time_completed * 100) + (late_completed * 70)
        performance_score = round(
            (weighted_completed_points / eligible_for_scoring), 1
        ) if eligible_for_scoring else 0

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
            'eligible_for_scoring': eligible_for_scoring,
            'performance_score': performance_score,
        }

    performance_data = []

    for staff in staff_users:
        assigned_tasks = UserTask.objects.filter(
            assigned_to=staff
        ).select_related('task', 'assigned_by')
        assigned_tasks = apply_date_filters(assigned_tasks)

        assigned_stats = summarize_tasks(assigned_tasks)

        completion_rate = assigned_stats['completion_rate']
        on_time_rate = assigned_stats['on_time_rate']
        performance_score = round(
            assigned_stats['performance_score'], 1
        ) if assigned_stats['eligible_for_scoring'] else 0

        performance_data.append({
            'staff': staff,
            'total_tasks': assigned_stats['total'],
            'completed_tasks': assigned_stats['completed'],
            'pending_tasks': assigned_stats['pending'],
            'overdue_tasks': assigned_stats['overdue'],
            'on_time_completed': assigned_stats['on_time_completed'],
            'late_completed': assigned_stats['late_completed'],
            'rejected_tasks': assigned_stats['rejected'],
            'completion_rate': completion_rate,
            'on_time_rate': on_time_rate,
            'eligible_for_scoring': assigned_stats['eligible_for_scoring'],
            'performance_score': performance_score,
            'assigned_tasks': assigned_tasks,
        })

    performance_data.sort(
        key=lambda item: (
            item['performance_score'],
            item['on_time_rate'],
            item['completed_tasks'],
            -item['overdue_tasks']
        ),
        reverse=True
    )

    grouped_performance_data = []
    for staff_type, label in User.STAFF_TYPE_CHOICES:
        group_items = [item for item in performance_data if item['staff'].staff_type == staff_type]
        if group_items:
            grouped_performance_data.append({
                'key': staff_type,
                'label': label,
                'items': group_items,
                'summary': {
                    'staff_count': len(group_items),
                    'total_tasks': sum(item['total_tasks'] for item in group_items),
                    'completed_tasks': sum(item['completed_tasks'] for item in group_items),
                    'pending_tasks': sum(item['pending_tasks'] for item in group_items),
                    'overdue_tasks': sum(item['overdue_tasks'] for item in group_items),
                    'on_time_completed': sum(item['on_time_completed'] for item in group_items),
                    'late_completed': sum(item['late_completed'] for item in group_items),
                },
            })

    unclassified_items = [item for item in performance_data if not item['staff'].staff_type]
    if unclassified_items:
        grouped_performance_data.append({
            'key': 'unclassified',
            'label': 'Unclassified Staff',
            'items': unclassified_items,
            'summary': {
                'staff_count': len(unclassified_items),
                'total_tasks': sum(item['total_tasks'] for item in unclassified_items),
                'completed_tasks': sum(item['completed_tasks'] for item in unclassified_items),
                'pending_tasks': sum(item['pending_tasks'] for item in unclassified_items),
                'overdue_tasks': sum(item['overdue_tasks'] for item in unclassified_items),
                'on_time_completed': sum(item['on_time_completed'] for item in unclassified_items),
                'late_completed': sum(item['late_completed'] for item in unclassified_items),
            },
        })

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
            'section': section_filter,
            'staff_type': staff_type_filter,
        },
        'section_choices': User.SECTION_CHOICES,
        'staff_type_choices': User.STAFF_TYPE_CHOICES,
        'grouped_performance_data': grouped_performance_data,
    })

@login_required
def staff_detail(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff')
    own_tasks = UserTask.objects.filter(
        assigned_to=staff,
        assigned_by=staff,
    ).select_related('task', 'assigned_by')

    if request.user.is_superuser:
        manager_tasks = UserTask.objects.filter(
            assigned_to=staff,
            assigned_by=request.user,
        ).select_related('task', 'assigned_by')
        manager_tasks_heading = "Tasks Assigned By You"
    elif request.user.role == 'manager':
        if staff.section != request.user.section:
            return HttpResponseForbidden()
        manager_tasks = UserTask.objects.filter(
            assigned_to=staff,
            assigned_by=request.user,
        ).select_related('task', 'assigned_by')
        manager_tasks_heading = "Tasks Assigned By You"
    elif request.user.role == 'staff':
        if staff.section != request.user.section:
            return HttpResponseForbidden()
        manager_tasks = UserTask.objects.filter(
            assigned_to=staff,
        ).exclude(assigned_by=staff).select_related('task', 'assigned_by')
        manager_tasks_heading = "Tasks Assigned By Manager"
    else:
        return HttpResponseForbidden()

    context = {
        'staff': staff,
        'all_tasks': own_tasks,
        'manager_tasks': manager_tasks,
        'manager_tasks_heading': manager_tasks_heading,
        'total_task_count': own_tasks.count() + manager_tasks.count(),
        'own_task_count': own_tasks.count(),
        'manager_task_count': manager_tasks.count(),
        'completed_count': own_tasks.filter(status='completed').count() + manager_tasks.filter(status='completed').count(),
        'pending_count': own_tasks.filter(status__in=['pending', 'in_progress', 'accepted']).count() + manager_tasks.filter(status__in=['pending', 'in_progress', 'accepted']).count(),
        'overdue_count': own_tasks.filter(task__due_date__lt=today).exclude(status__in=['completed', 'rejected', 'accepted']).count() + manager_tasks.filter(task__due_date__lt=today).exclude(status__in=['completed', 'rejected', 'accepted']).count(),
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

@login_required
def category_users_json(request):
    category_id = request.GET.get('category_id')

    users = []

    if category_id:
        members = CategoryMember.objects.filter(
            category_id=category_id
        ).select_related('user')

        if request.user.is_authenticated and not request.user.is_superuser:
            members = members.filter(
                user__section=request.user.section,
                user__role='staff',
                user__is_active=True,
            )

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
