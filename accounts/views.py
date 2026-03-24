# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from .models import User


@login_required
def add_user(request):
    section_choices = User.SECTION_CHOICES

    if request.method == 'POST':
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Default role/section
        if request.user.is_superuser:
            section = request.POST.get('section')
            role = request.POST.get('role')
        elif request.user.role == 'manager':
            section = request.user.section   # force same section
            role = 'staff'                   # force staff
        else:
            return HttpResponseForbidden("Not allowed")

        # VALIDATIONS
        if not all([email, password1, password2]):
            messages.error(request, "All fields are required.")

        elif password1 != password2:
            messages.error(request, "Passwords do not match.")

        elif User.objects.filter(email=email).exists():
            messages.error(request, "User already exists.")

        else:
            User.objects.create_user(
                email=email,
                section=section,
                role=role,
                password=password1,
            )
            messages.success(request, f"{email} created successfully")
            return redirect('add_user')

    return render(request, 'accounts/add_user.html', {
        'section_choices': section_choices
    })


@login_required
def manage_users(request):
    if request.user.role != 'manager' and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to manage users.")

    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role')
    section_filter = request.GET.get('section')
    status_filter = request.GET.get('status')

    # Superuser sees all users, manager sees only their section staff
    if request.user.is_superuser:
        users = User.objects.all().order_by('-id')
    else:
        users = User.objects.filter(
            section=request.user.section,
            role='staff'
        ).order_by('-id')

    # Apply filters
    if query:
        users = users.filter(email__icontains=query)

    if role_filter:
        users = users.filter(role=role_filter)

    if section_filter and request.user.is_superuser:
        users = users.filter(section=section_filter)

    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    context = {
        'users': users,
        'section_choices': User.SECTION_CHOICES,
        'role_choices': [('manager', 'Manager'), ('staff', 'Staff')],
        'current_filters': {
            'q': query,
            'role': role_filter,
            'section': section_filter if request.user.is_superuser else request.user.section,
            'status': status_filter,
        }
    }

    return render(request, 'accounts/manage_users.html', context)


@login_required
def toggle_user_active(request, user_id):
    if request.user.role != 'manager' and not request.user.is_superuser:
        return HttpResponseForbidden()

    user = get_object_or_404(User, id=user_id)

    if not request.user.is_superuser:
        if user.section != request.user.section or user.role != 'staff':
            return HttpResponseForbidden("Not allowed")

    if user == request.user:
        messages.error(request, "You cannot deactivate yourself.")
        return redirect('manage_users')

    user.is_active = not user.is_active
    user.save()
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User {user.email} has been {status}.")
    return redirect('manage_users')


@login_required
def delete_user(request, user_id):
    if request.user.role != 'manager' and not request.user.is_superuser:
        return HttpResponseForbidden()

    user = get_object_or_404(User, id=user_id)

    if not request.user.is_superuser:
        if user.section != request.user.section or user.role != 'staff':
            return HttpResponseForbidden("Not allowed")

    if user == request.user:
        messages.error(request, "You cannot delete yourself.")
        return redirect('manage_users')

    user.delete()
    messages.success(request, f"User {user.email} deleted successfully.")
    return redirect('manage_users')


# login view
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid email or password")

    return render(request, "accounts/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")