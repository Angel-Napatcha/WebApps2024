from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from register.models import UserAccount

# Form for creating a new account
class UserRegistrationForm(UserCreationForm):
    # Additional fields for first name, last name, and email
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))
    email = forms.EmailField(max_length=75, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Email'}))

    # Add placeholder
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Username'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm Password'})

    # Clean the username field and check for existing users with the same username
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    # Clean the email field and check for existing users with the same email
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    # Clean the password fields and check if they match
    def clean_password(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields didn't match.")

    class Meta:
        # Specify the User model and the fields to include in the form
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')


class UserAccountForm(forms.ModelForm):
    class Meta:
        model = UserAccount
        fields = ('preferred_currency',)
        

def register_view(request):
    if request.method == 'POST':
        # Create instances of the UserRegistrationForm and UserAccountForm with the submitted data
        user_form = UserRegistrationForm(request.POST)
        account_form = UserAccountForm(request.POST)
        
        # Check if both forms are valid
        if user_form.is_valid() and account_form.is_valid():
            # Save the user instance but don't save it yet
            new_user = user_form.save()
            
            # Save the user instance but don't save it yet
            account = account_form.save(commit=False)
            
            # Set the user for the UserAccount instance
            account.user = new_user
            
            # Set the account as not activated
            account.is_activated = False
            
            # Save the UserAccount instance
            account.save()
            
            # Send verification email
            token = default_token_generator.make_token(new_user)
            uid = urlsafe_base64_encode(force_bytes(new_user.pk))
            link = request.build_absolute_uri(reverse('activate', kwargs={'uidb64': uid, 'token': token}))
            email_body = f'Hi {new_user.username}, please use this link to verify your email address: {link}'
            send_mail(
                'Verify your email address',
                email_body,
                'from@example.com',
                [new_user.email],
                fail_silently=False,
            )
            # Redirect to the account verification page
            return redirect('account_verification')
    else:
        user_form = UserRegistrationForm()
        account_form = UserAccountForm()
    
    # Render the registration template with the form instances
    return render(request, 'register/register.html', {'user_form': user_form, 'account_form': account_form})

def verify_account(request):
    # Render the account verification template
    return render(request, 'register/account_verification.html')

def activate(request, uidb64, token):
    try:
        # Decode the base64 encoded user ID
        uid = urlsafe_base64_decode(uidb64).decode()
        # Get the User object from the decoded user ID
        user = User.objects.get(pk=uid)
        # Get the UserAccount object associated with the User
        user_account = UserAccount.objects.get(user=user)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, UserAccount.DoesNotExist):
        # If any exception is raised, render the activation_invalid.html template
        return render(request, 'register/activation_invalid.html')

    # Check if the User exists, token is valid, and UserAccount is not activated
    if user is not None and default_token_generator.check_token(user, token) and not user_account.is_activated:
        # Activate the User by setting 'is_active' to True
        user.is_active = True
        user.save()
        
        # Activate the UserAccount by setting 'is_activated' to True
        user_account.is_activated = True
        user_account.save()
        
        # Render the activation_success.html template
        return render(request, 'register/activation_success.html') 
    else:
        # If conditions are not met, render the activation_invalid.html template
        return render(request, 'register/activation_invalid.html')

def is_admin(user):
    # Check if the user is active, staff, and superuser
    return user.is_active and user.is_staff and user.is_superuser

def login_view(request):
    if request.method == 'POST':
        # Get the username and password from the request
        username = request.POST['username']
        password = request.POST['password']
               
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        
        # If the user is authenticated
        if user is not None:
            # Check if the user is an admin
            if is_admin(user):
                # Log in the admin user
                login(request, user)
                # Redirect the admin user to the admin home page
                return redirect('/webapps2024/payapp/admin/home/')
            
            # Check if the user's account is activated
            if UserAccount.objects.get(user=user).is_activated:
                # Log in the user
                login(request, user)
                # Redirect the user to the home page
                return redirect('/webapps2024/payapp/home')
            else:
                # Render the login template with an error message
                return render(request, 'register/login.html', {'error': 'Account is not activated, please check your email.'})
        else:
            # Render the login template with an error message
            return render(request, 'register/login.html', {'error': 'Invalid username or password.'})
    else:
        return render(request, 'register/login.html')

def register_admin_view(request):
    # Check if the current user is an admin. If not, return a 403 Forbidden response
    if not is_admin(request.user):
        return HttpResponse('You do not have the necessary permissions to view this page.', status=403)
    if request.method == 'POST':
        # Create an instance of the UserRegistrationForm with the submitted data
        admin_form = UserRegistrationForm(request.POST)
        if admin_form.is_valid():
            # Create a new user instance but don't save it yet
            new_admin = admin_form.save(commit=False)
            
            # Set the user as active, staff, and superuser
            new_admin.is_active = True
            new_admin.is_staff = True
            new_admin.is_superuser = True
            
            # Save the new admin user
            new_admin.save()
            
            # Redirect to the 'register_admin_success' URL
            return redirect('register_admin_success')
    else:
        admin_form = UserRegistrationForm()
    
    # Render the register_admin.html template with the form instance
    return render(request, 'register/register_admin.html', {'admin_form': admin_form})

def register_admin_success(request):
    return render(request, 'register/register_admin_success.html')