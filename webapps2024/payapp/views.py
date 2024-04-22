from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django import forms
from django.http import HttpResponse
from payapp.models import Transaction
from register.models import UserAccount
from currency_converter_api.views import convert_currency
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class TransactionForm(forms.Form):
    recipient_email = forms.EmailField(max_length=30, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter recipient email', 'class': 'form-group'}))
    amount = forms.DecimalField(decimal_places=2, max_digits=10, widget=forms.NumberInput(attrs={'placeholder': 'Enter amount', 'class': 'form-group', 'step': '0.01'}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(TransactionForm, self).__init__(*args, **kwargs)
        self.fields['recipient_email'].validators.append(self.validate_recipient_email)
        self.fields['amount'].validators.append(self.validate_amount)

    def validate_recipient_email(self, email):
        try:
            recipient = User.objects.get(email=email)
            UserAccount.objects.get(user=recipient)
        except User.DoesNotExist:
            raise ValidationError('Recipient not found.')
        except UserAccount.DoesNotExist:
            raise ValidationError('Recipient has no associated account.')
        return email

    def validate_amount(self, amount):
        if amount <= 0:
            raise ValidationError("The amount must be greater than zero.")
        sender_account = UserAccount.objects.get(user=self.user)
        if sender_account.balance < amount:
            raise ValidationError("The amount exceeds your current balance.")
        return amount

def home_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    user_account = request.user.useraccount
    balance = user_account.balance
    preferred_currency = user_account.preferred_currency

    context = {
        'user': request.user,
        'balance': "{:,.2f}".format(balance),  
        'currency': preferred_currency
    }
    return render(request, 'payapp/home.html', context)

def transaction_view(request):
    user = request.user
    form = TransactionForm(request.POST or None, user=user)
    if request.method == 'POST' and form.is_valid():
        recipient_email = form.cleaned_data['recipient_email']
        amount = form.cleaned_data['amount']
        recipient = User.objects.get(email=recipient_email)
        recipient_account = UserAccount.objects.get(user=recipient)
        sender_account = UserAccount.objects.get(user=user)

        amount_received = amount
        if sender_account.preferred_currency != recipient_account.preferred_currency:
            amount_received = convert_currency(sender_account.preferred_currency, recipient_account.preferred_currency, amount)
        
        sender_account.balance -= amount
        recipient_account.balance += amount_received
        sender_account.save()
        recipient_account.save()
        
        Transaction.objects.create(sender=user, recipient=recipient, amount_sent=amount, amount_received=amount_received, timestamp=timezone.now(), status='Completed')
        
        return redirect('transaction_complete')

    return render(request, 'payapp/transaction.html', {'form': form})

def transaction_complete_view(request):
    return render(request, 'payapp/transaction_complete.html')

def logout_view(request):
    logout(request)
    return redirect('login')