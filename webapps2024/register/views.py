from django.shortcuts import render, redirect
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from register.models import UserAccount
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True,
                                 widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=30, required=True,
                                widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))
    email = forms.EmailField(max_length=75, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Email'}))

    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Username'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm Password'})

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with that username already exists")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists")
        return email

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')


class UserAccountForm(forms.ModelForm):
    class Meta:
        model = UserAccount
        fields = ('preferred_currency',)


def register_view(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        account_form = UserAccountForm(request.POST)
        if user_form.is_valid() and account_form.is_valid():
            new_user = user_form.save()
            account = account_form.save(commit=False)
            account.user = new_user
            account.is_activated = False 
            account.save()
            
            # Send verification email
            token = default_token_generator.make_token(new_user)
            uid = urlsafe_base64_encode(force_bytes(new_user.pk))
            link = request.build_absolute_uri(reverse('activate', kwargs={'uidb64': uid, 'token': token}))
            email_body = f'Hi {new_user.username}, Please use this link to verify your email address: {link}'
            send_mail(
                'Verify your email address',
                email_body,
                'from@example.com',
                [new_user.email],
                fail_silently=False,
            )
            return redirect('account_verification') 
            
    else:
        user_form = UserRegistrationForm()
        account_form = UserAccountForm()
    return render(request, 'register/register.html', {'user_form': user_form, 'account_form': account_form})

def account_verification(request):
    return render(request, 'register/account_verification.html')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
        user_account = UserAccount.objects.get(user=user)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, UserAccount.DoesNotExist):
        return render(request, 'register/activation_invalid.html')

    if user is not None and default_token_generator.check_token(user, token) and not user_account.is_activated:
        user.is_active = True
        user.save()
        user_account.is_activated = True
        user_account.save()
        return render(request, 'register/activation_success.html') 
    else:
        return render(request, 'register/activation_invalid.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if UserAccount.objects.get(user=user).is_activated:
                login(request, user)
                return redirect('/webapps2024/payapp/home')
            else:
                return render(request, 'register/login.html', {'error': 'Account is not activated, please check your email.'})
        else:
            return render(request, 'register/login.html', {'error': 'Invalid username or password'})
    else:
        return render(request, 'register/login.html')