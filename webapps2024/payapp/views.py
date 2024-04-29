from django.shortcuts import render, redirect
from django.contrib.auth import logout
from currency_converter_api.views import convert_currency
from django.http import JsonResponse
from django import forms
from django.http import HttpResponse
from register.models import UserAccount
from payapp.models import Transaction, PaymentRequest, Notification
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction


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
            if recipient.email == self.user.email:
                raise ValidationError('You cannot send money to your own account.')
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


class PaymentRequestForm(forms.Form):
    recipient_email = forms.EmailField(max_length=30, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter recipient email', 'class': 'form-group'}))
    amount = forms.DecimalField(decimal_places=2, max_digits=10, widget=forms.NumberInput(attrs={'placeholder': 'Enter amount', 'class': 'form-group', 'step': '0.01'}))
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'Enter message (optional)', 'class': 'form-group', 'rows': '3'}))
    
    def __init__(self, *args, **kwargs):
        self.requester = kwargs.pop('requester', None)
        super(PaymentRequestForm, self).__init__(*args, **kwargs)

    def clean_recipient_email(self):
        email = self.cleaned_data.get('recipient_email')
        if email == self.requester.email:
            raise forms.ValidationError("You cannot request money from yourself.")
        try:
            self.recipient = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("A user with this email does not exist.")
        return email

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("The amount must be greater than zero.")
        return amount

def home_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    user_account = request.user.useraccount
    balance = user_account.balance
    preferred_currency = user_account.preferred_currency
    currency_symbols = {
        'USD': '$', 
        'EUR': '€', 
        'GBP': '£',
    }
    preferred_currency_symbol = currency_symbols.get(preferred_currency, '')

    # Fetch transactions for the logged-in user
    transactions = Transaction.objects.filter(
        sender=request.user,
        status='Successful'
    ).union(
        Transaction.objects.filter(recipient=request.user, status='Successful')
    ).order_by('-timestamp')

     # Prepare the data for the template
    transaction_data = []
    for transaction in transactions:
        if transaction.sender == request.user:
            transaction_type = 'Sent'
            other_party = transaction.recipient.useraccount
            sign = '-'
            currency_symbol = currency_symbols.get(transaction.currency_sent, '')
            amount = f"{sign}{currency_symbol}{transaction.amount_sent:.2f}"
        else:
            transaction_type = 'Received'
            other_party = transaction.sender.useraccount
            sign = '+'
            currency_symbol = currency_symbols.get(transaction.currency_received, '')
            amount = f"{sign}{currency_symbol}{transaction.amount_received:.2f}"

        transaction_data.append({
            'username': other_party.user.username,
            'amount': amount,
            'date': transaction.timestamp.strftime('%Y-%m-%d %H:%M'),
            'type': transaction_type
        })
        
    # Fetch payment requests
    sent_requests = PaymentRequest.objects.filter(requester=request.user).order_by('-timestamp')
    received_requests = PaymentRequest.objects.filter(recipient=request.user).order_by('-timestamp')

    sent_request_data = [{
        'recipient': req.recipient.username,
        'amount': f"{currency_symbols.get(req.requester.useraccount.preferred_currency, '')}{req.amount_requested:.2f}",
        'message': req.message,
        'date': req.timestamp.strftime('%Y-%m-%d %H:%M'),
        'status': req.status
    } for req in sent_requests]

    received_request_data = [{
        'id': req.id,
        'requester': req.requester.username,
        'amount': f"{currency_symbols.get(req.recipient.useraccount.preferred_currency, '')}{req.amount_in_recipient_currency:.2f}",
        'message': req.message,
        'date': req.timestamp.strftime('%Y-%m-%d %H:%M'),
        'status': req.status
    } for req in received_requests]
    
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    unread_notifications_count = Notification.objects.filter(recipient=request.user, read=False).count()

    context = {
        'user': request.user,
        'balance': f"{preferred_currency_symbol}{balance:,.2f}",
        'currency': preferred_currency_symbol,
        'transactions': transaction_data,
        'sent_requests': sent_request_data,
        'received_requests': received_request_data,
        'notifications': notifications,
        'unread_notifications_count' : unread_notifications_count
    }

    return render(request, 'payapp/home.html', context)

def transaction_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    user = request.user
    form = TransactionForm(request.POST or None, user=user)
    
    if request.method == 'POST' and form.is_valid():
        recipient_email = form.cleaned_data['recipient_email']
        amount_sent = form.cleaned_data['amount']
        recipient = User.objects.get(email=recipient_email)
        sender_account = UserAccount.objects.get(user=user)
        
        sender_account.balance -= amount_sent
        sender_account.save()
        
        # Fetch currency details
        currency_sent = sender_account.preferred_currency
        currency_received = UserAccount.objects.get(user=recipient).preferred_currency

        if currency_sent != currency_received:
           amount_received = convert_currency(currency_sent, currency_received, amount_sent)
        else:
            amount_received = amount_sent
        
        recipient_account = UserAccount.objects.get(user=recipient)
        recipient_account.balance += amount_received
        recipient_account.save()

        # Create a new transaction
        Transaction.objects.create(
            sender=user,
            recipient=recipient,
            amount_sent=amount_sent,
            amount_received=amount_received,
            timestamp=timezone.now(),
            status='Successful'
        )
        
        return redirect('transaction_complete')

    return render(request, 'payapp/transaction.html', {'form': form})

def transaction_complete_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    last_transaction = Transaction.objects.filter(sender=request.user).order_by('timestamp').last()
    
    # Retrieve the preferred currency from the UserAccount model
    user_account = UserAccount.objects.get(user=request.user)
    preferred_currency_symbol = user_account.preferred_currency 
    
    context = {
        'currency_symbol': preferred_currency_symbol,
        'amount_sent': last_transaction.amount_sent,
        'recipient_email': last_transaction.recipient.email,
        'timestamp': last_transaction.timestamp.strftime('%B %d, %Y, %H:%M %p'),  # Format date as needed
    }

    return render(request, 'payapp/transaction_complete.html', context)

def request_payment_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    user = request.user
    form = PaymentRequestForm(request.POST or None, requester=user)
    currency_symbols = {
        'USD': '$', 
        'EUR': '€', 
        'GBP': '£',
    }
    
    if request.method == 'POST' and form.is_valid():
        recipient_email = form.cleaned_data['recipient_email']
        recipient = User.objects.get(email=recipient_email)
        amount = form.cleaned_data['amount']
        message = form.cleaned_data.get('message', '')
        
        # Fetch the sender and recipient currency details
        sender_account = UserAccount.objects.get(user=recipient)
        recipient_account = UserAccount.objects.get(user=user)
        sender_currency_symbol = currency_symbols.get(sender_account.preferred_currency, '')
        
        # Convert the amount if the currencies are different
        if sender_account.preferred_currency != recipient_account.preferred_currency:
            amount_sent = convert_currency(recipient_account.preferred_currency, sender_account.preferred_currency, amount)
        else:
            amount_sent = amount

        transaction = Transaction.objects.create(
            sender=recipient,
            recipient=user,
            amount_sent=amount_sent,
            amount_received=amount,
            timestamp=timezone.now(),
            status='Pending'
        )

        PaymentRequest.objects.create(
            requester=user,
            recipient=recipient,
            transaction=transaction,
            amount_requested=amount,
            amount_in_recipient_currency=amount_sent,
            message=message,
            timestamp=timezone.now(),
            status='Pending'
        )

        formatted_amount = "{:.2f}".format(amount_sent)
        
        Notification.objects.create(
            recipient=recipient,
            message=f"You have received a payment request of {sender_currency_symbol}{formatted_amount} from {user.username}.",
            read=False,
            timestamp=timezone.now()
        )

        return redirect('request_complete')  # Redirect to a success page after submission

    return render(request, 'payapp/payment_request.html', {'form': form})

def request_payment_complete_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    last_request = PaymentRequest.objects.filter(requester=request.user).order_by('timestamp').last()
    
    # Retrieve the preferred currency from the UserAccount model
    user_account = UserAccount.objects.get(user=request.user)
    preferred_currency_symbol = user_account.preferred_currency 
    
    context = {
        'currency_symbol': preferred_currency_symbol,
        'amount_requested': last_request.amount_requested,
        'recipient_email': last_request.recipient.email,
        'timestamp': last_request.timestamp.strftime('%B %d, %Y, %H:%M %p'),  # Format date as needed
    }

    return render(request, 'payapp/payment_request_complete.html', context)

def handle_payment_request_view(request, request_id):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    payment_request = get_object_or_404(PaymentRequest, id=request_id)

    if payment_request.recipient != request.user:
        return HttpResponse('You are not authorized to handle this payment request.', status=403)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            return accept_payment_request(request, payment_request)
        elif action == 'reject':
            return reject_payment_request(request, payment_request)

    # Render the home template with the payment request details
    context = {
        'payment_request': payment_request,
    }
    return render(request, 'payapp/home.html', context)

def accept_payment_request(request, payment_request):
    sender_account = UserAccount.objects.get(user=payment_request.transaction.sender)
    recipient_account = UserAccount.objects.get(user=payment_request.transaction.recipient)
    currency_symbols = {
        'USD': '$', 
        'EUR': '€', 
        'GBP': '£',
    }
    currency_symbol = currency_symbols.get(recipient_account.preferred_currency, '')

    if sender_account.balance < payment_request.transaction.amount_sent:
        return HttpResponse('<p>Insufficient funds to complete this transaction.</p>', status=400)

    with transaction.atomic():
        payment_request.transaction.status = 'Successful'
        payment_request.transaction.save()
        
        payment_request.status = 'Approved'
        payment_request.save()

        sender_account.balance -= payment_request.transaction.amount_sent
        sender_account.save()
        recipient_account.balance += payment_request.transaction.amount_received
        recipient_account.save()
        
        Notification.objects.create(
        recipient=payment_request.requester,
        message=f'Your payment request of {currency_symbol}{payment_request.transaction.amount_received} to {payment_request.transaction.sender} has been approved.',
        read=False
        )

    return redirect('home')

def reject_payment_request(request, payment_request):
    recipient_account = UserAccount.objects.get(user=payment_request.transaction.recipient)
    currency_symbols = {
        'USD': '$', 
        'EUR': '€', 
        'GBP': '£',
    }
    currency_symbol = currency_symbols.get(recipient_account.preferred_currency, '')
    
    with transaction.atomic():
        payment_request.transaction.status = 'Failed'
        payment_request.transaction.save()
        
        payment_request.status = 'Rejected'
        payment_request.save()
        
        Notification.objects.create(
        recipient=payment_request.requester,
        message=f'Your payment request of {currency_symbol}{payment_request.transaction.amount_received} to {payment_request.transaction.sender} has been rejected.',
        read=False
        )

    return redirect('home')

def notifications_view(request):
     # Retrieve unread notifications for the logged-in user
    notifications = Notification.objects.filter(recipient=request.user, read=False).order_by('-timestamp')
    
    # Mark notifications as read
    notifications.update(read=True)

    # Serialize the notifications data
    notifications_data = [{
        'id': notification.id,
        'message': notification.message,
        'read': notification.read,
        'timestamp': notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for notification in notifications]

    # Return the serialized data as JSON
    return JsonResponse({'notifications': notifications_data})

def logout_view(request):
    logout(request)
    return redirect('login')