# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import User


def add_user(request):
    section_choices = User.SECTION_CHOICES

    if request.method == 'POST':
        email = request.POST.get('email')
        section = request.POST.get('section')
        print(section)
        role = request.POST.get('role')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Validations
        if not all([email, section, role, password1, password2]):
            messages.error(request, "All fields are required.")
        elif password1 != password2:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "User with this email already exists.")
        elif section not in dict(User.SECTION_CHOICES):
            messages.error(request, "Invalid section selected.")
        else:
            user = User.objects.create_user(
                email=email,
                section=section,
                role=role,
                password=password1,
            )
            messages.success(request, f"User {email} created successfully!")
            return redirect('add_user')

    return render(
        request,
        'accounts/add_user.html',
        {'section_choices': section_choices}
    )


#login view
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