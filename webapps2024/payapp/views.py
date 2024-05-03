from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from currency_converter_api.views import convert_currency
from register.views import is_admin
from register.models import UserAccount
from payapp.models import Transaction, PaymentRequest, Notification


# Form for creating transactions
class TransactionForm(forms.Form):
    recipient_email = forms.EmailField(max_length=30, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter recipient email', 'class': 'form-group'}))
    amount = forms.DecimalField(decimal_places=2, max_digits=10, widget=forms.NumberInput(attrs={'placeholder': 'Enter amount', 'class': 'form-group', 'step': '0.01'}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(TransactionForm, self).__init__(*args, **kwargs)
        self.fields['recipient_email'].validators.append(self.validate_recipient_email)
        self.fields['amount'].validators.append(self.validate_amount)

    # Ensure the recipient exists and is not the sender
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

    # Ensure the amount is positive and the sender has enough balance to make the transaction
    def validate_amount(self, amount):
        if amount <= 0:
            raise ValidationError("The amount must be greater than zero.")
        sender_account = UserAccount.objects.get(user=self.user)
        if sender_account.balance < amount:
            raise ValidationError("The amount exceeds your current balance.")
        return amount


# Form for creating payment requests
class PaymentRequestForm(forms.Form):
    recipient_email = forms.EmailField(max_length=30, required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter recipient email', 'class': 'form-group'}))
    amount = forms.DecimalField(decimal_places=2, max_digits=10, widget=forms.NumberInput(attrs={'placeholder': 'Enter amount', 'class': 'form-group', 'step': '0.01'}))
    message = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'Enter message (optional)', 'class': 'form-group', 'rows': '3'}))
    
    def __init__(self, *args, **kwargs):
        self.requester = kwargs.pop('requester', None)
        super(PaymentRequestForm, self).__init__(*args, **kwargs)

    # Ensure the recipient exists and is not the requester
    def clean_recipient_email(self):
        email = self.cleaned_data.get('recipient_email')
        if email == self.requester.email:
            raise forms.ValidationError("You cannot request money from yourself.")
        try:
            self.recipient = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("A user with this email does not exist.")
        return email

    # Ensure the amount is positive 
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("The amount must be greater than zero.")
        return amount


# Dictionary to map currency codes to symbols
currency_symbols = {
        'USD': '$', 
        'EUR': '€', 
        'GBP': '£',
    }

def home_view(request):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    # Fetch user account and transaction data
    user_account = request.user.useraccount
    balance = user_account.balance
    preferred_currency = user_account.preferred_currency
    preferred_currency_symbol = currency_symbols.get(preferred_currency, '')

    # Fetch and combine transactions where the user is sender or recipient
    transactions = Transaction.objects.filter(
        sender=request.user,
        status='Successful'
    ).union(
        Transaction.objects.filter(recipient=request.user, status='Successful')
    ).order_by('-timestamp')

    # Compile transaction data for display
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

    # Compile payment requests the user sent and received
    sent_request_data = [{
        'recipient': req.recipient.username,
        'amount': f"{currency_symbols.get(req.requester.useraccount.preferred_currency, '')}{req.amount_requested:.2f}",
        'message': req.message,
        'date': req.timestamp.strftime('%B %d, %Y, %H:%M %p'),
        'status': req.status
    } for req in sent_requests]

    received_request_data = [{
        'id': req.id,
        'requester': req.requester.username,
        'amount': f"{currency_symbols.get(req.recipient.useraccount.preferred_currency, '')}{req.amount_in_recipient_currency:.2f}",
        'message': req.message,
        'date': req.timestamp.strftime('%B %d, %Y, %H:%M %p'),
        'status': req.status
    } for req in received_requests]
    
    # Fetch notifications
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    unread_notifications_count = Notification.objects.filter(recipient=request.user, read=False).count()

    # Prepare context data for the template
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

    # Render the home template with the context data
    return render(request, 'payapp/home.html', context)

def transaction_view(request):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    # Fetch the user account
    user = request.user
    
    # Initialise the TransactionForm with the user instance
    form = TransactionForm(request.POST or None, user=user)
    
    if request.method == 'POST' and form.is_valid():
        # Get the recipient email and amount from the cleaned form data
        recipient_email = form.cleaned_data['recipient_email']
        amount_sent = form.cleaned_data['amount']
        
        # Get the recipient user object based on the email
        recipient = User.objects.get(email=recipient_email)
        
        # Get the sender's user account
        sender_account = UserAccount.objects.get(user=user)
        
        # Deduct the amount from the sender's account balance
        sender_account.balance -= amount_sent
        sender_account.save()
        
        # Fetch the sender and recipient currencies
        currency_sent = sender_account.preferred_currency
        currency_received = UserAccount.objects.get(user=recipient).preferred_currency

        # If the currencies are different, convert the amount
        if currency_sent != currency_received:
           amount_received = convert_currency(currency_sent, currency_received, amount_sent)
        else:
            amount_received = amount_sent
        
        # Get the recipient's user account
        recipient_account = UserAccount.objects.get(user=recipient)
        
        # Add the amount to the recipient's account balance
        recipient_account.balance += amount_received
        recipient_account.save()

        # Create a new transaction record
        Transaction.objects.create(
            sender=user,
            recipient=recipient,
            amount_sent=amount_sent,
            amount_received=amount_received,
            timestamp=timezone.now(),
            status='Successful'
        )
        
        # Redirect to the transaction complete view
        return redirect('transaction_complete')

    # Render the transaction template with the form instance
    return render(request, 'payapp/transaction.html', {'form': form})

def transaction_complete_view(request):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    # Fetch the user's last transaction
    last_transaction = Transaction.objects.filter(sender=request.user).order_by('timestamp').last()
    
    # Retrieve the user's preferred currency from the UserAccount model
    user_account = UserAccount.objects.get(user=request.user)
    preferred_currency_symbol = user_account.preferred_currency 
    
    # Prepare context data for the template
    context = {
        'currency_symbol': preferred_currency_symbol,
        'amount_sent': last_transaction.amount_sent,
        'recipient_email': last_transaction.recipient.email,
        'timestamp': last_transaction.timestamp.strftime('%B %d, %Y, %H:%M %p'), 
    }

    # Render the transaction_complete template with the context data
    return render(request, 'payapp/transaction_complete.html', context)

def request_payment_view(request):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    # Fetch the user account
    user = request.user
    
    # Initialise the PaymentRequestForm with the user instance
    form = PaymentRequestForm(request.POST or None, requester=user)
    
    if request.method == 'POST' and form.is_valid():
        # Get the recipient email, amount, and optional message from the cleaned form data
        recipient_email = form.cleaned_data['recipient_email']
        recipient = User.objects.get(email=recipient_email)
        amount = form.cleaned_data['amount']
        message = form.cleaned_data.get('message', '')
        
        # Fetch the sender (recipient of the payment request) and recipient (requester) currency details
        sender_account = UserAccount.objects.get(user=recipient)
        recipient_account = UserAccount.objects.get(user=user)
        sender_currency_symbol = currency_symbols.get(sender_account.preferred_currency, '')
        
        # Convert the amount if the currencies are different
        if sender_account.preferred_currency != recipient_account.preferred_currency:
            amount_sent = convert_currency(recipient_account.preferred_currency, sender_account.preferred_currency, amount)
        else:
            amount_sent = amount

        # Create a new pending transaction
        transaction = Transaction.objects.create(
            sender=recipient,
            recipient=user,
            amount_sent=amount_sent,
            amount_received=amount,
            timestamp=timezone.now(),
            status='Pending'
        )

        # Create a new payment request
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

        # Format the amount for the notification message
        formatted_amount = "{:.2f}".format(amount_sent)
        
        # Create a new notification for the recipient
        Notification.objects.create(
            recipient=recipient,
            message=f"You have received a payment request of {sender_currency_symbol}{formatted_amount} from {user.username}.",
            read=False,
            timestamp=timezone.now()
        )

        # Redirect to the request_payment_complete_view after successful submission
        return redirect('request_complete')  # Redirect to a success page after submission

    # Render the payment_request template with the form instance
    return render(request, 'payapp/payment_request.html', {'form': form})

def request_payment_complete_view(request):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)
    
    # Fetch the user's last payment
    last_request = PaymentRequest.objects.filter(requester=request.user).order_by('timestamp').last()
    
    # Retrieve the preferred currency from the UserAccount model
    user_account = UserAccount.objects.get(user=request.user)
    preferred_currency_symbol = user_account.preferred_currency 
    
    # Prepare context data for the template
    context = {
        'currency_symbol': preferred_currency_symbol,
        'amount_requested': last_request.amount_requested,
        'recipient_email': last_request.recipient.email,
        'timestamp': last_request.timestamp.strftime('%B %d, %Y, %H:%M %p'), 
    }

    # Render the payment_request_complete template with the context data
    return render(request, 'payapp/payment_request_complete.html', context)

def handle_payment_request_view(request, request_id):
    # Require user authentication
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    # Fetch the payment request object by id, or return a 404 error if not found
    payment_request = get_object_or_404(PaymentRequest, id=request_id)

    # Check if the current user is the recipient of the payment request
    if payment_request.recipient != request.user:
        return HttpResponse('You are not authorized to handle this payment request.', status=403)

    if request.method == 'POST':
        action = request.POST.get('action')
        # If the action is 'accept', call the accept_payment_request function
        if action == 'accept':
            return accept_payment_request(request, payment_request)
        # If the action is 'reject', call the reject_payment_request function
        elif action == 'reject':
            return reject_payment_request(request, payment_request)

    # Prepare context data for the template
    context = {
        'payment_request': payment_request,
    }
    
    # Render the home template with the payment request details
    return render(request, 'payapp/home.html', context)

def accept_payment_request(request, payment_request):
    # Fetch the sender and recipient accounts
    sender_account = UserAccount.objects.get(user=payment_request.transaction.sender)
    recipient_account = UserAccount.objects.get(user=payment_request.transaction.recipient)
    
    # Get the recipient's preferred currency symbol
    currency_symbol = currency_symbols.get(recipient_account.preferred_currency, '')

    # Check if the sender has sufficient balance
    if sender_account.balance < payment_request.transaction.amount_sent:
        return HttpResponse('<p>Insufficient funds to complete this transaction.</p>', status=400)

    with transaction.atomic():
        # Update the transaction status to 'Successful'
        payment_request.transaction.status = 'Successful'
        payment_request.transaction.save()
        
        # Update the payment request status to 'Approved'
        payment_request.status = 'Approved'
        payment_request.save()

        # Deduct the amount from the sender's account
        sender_account.balance -= payment_request.transaction.amount_sent
        sender_account.save()
        
        # Add the amount to the recipient's account
        recipient_account.balance += payment_request.transaction.amount_received
        recipient_account.save()
        
        # Create a notification for the requester
        Notification.objects.create(
        recipient=payment_request.requester,
        message=f'Your payment request of {currency_symbol}{payment_request.transaction.amount_received} to {payment_request.transaction.sender} has been approved.',
        read=False
        )

    # Redirect to the home page
    return redirect('home')

def reject_payment_request(request, payment_request):
    # Fetch the recipient's account and curency symbol
    recipient_account = UserAccount.objects.get(user=payment_request.transaction.recipient)
    currency_symbol = currency_symbols.get(recipient_account.preferred_currency, '')
    
    with transaction.atomic():
        # Update the transaction status to 'Failed'
        payment_request.transaction.status = 'Failed'
        payment_request.transaction.save()
        
        # Update the payment request status to 'Rejected'
        payment_request.status = 'Rejected'
        payment_request.save()
        
        # Create a notification for the requester
        Notification.objects.create(
        recipient=payment_request.requester,
        message=f'Your payment request of {currency_symbol}{payment_request.transaction.amount_received} to {payment_request.transaction.sender} has been rejected.',
        read=False
        )

    # Redirect to the home page
    return redirect('home')

def notifications_view(request):
    # Retrieve unread notifications for the logged-in user
    notifications = Notification.objects.filter(recipient=request.user, read=False).order_by('-timestamp')
    
    # Mark notifications as read
    notifications.update(read=True)

    # Prepare notifications data for the template
    notifications_data = [{
        'id': notification.id,
        'message': notification.message,
        'read': notification.read,
        'timestamp': notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for notification in notifications]

    # Return the serialized notifications data as JSON
    return JsonResponse({'notifications': notifications_data})

def admin_home_view(request):
    # Check if the current user is an admin. If not, return a 403 Forbidden response
    if not is_admin(request.user):
        return HttpResponse('You do not have the necessary permissions to view this page.', status=403)

    # Fetch and enrich user accounts
    user_accounts = UserAccount.objects.all()
    
    # Enrich the user account objects with currency symbol and user email
    for account in user_accounts:
        account.currency_symbol = currency_symbols.get(account.preferred_currency, '')
        account.user_email = account.user.email

    # Fetch all transactions from the database, ordered by timestamp in descending order
    transactions = Transaction.objects.all().order_by('-timestamp')

    # Enrich the transaction objects with sender and recipient currency symbols, and format the timestamp
    for transaction in transactions:
        transaction.sender_currency_symbol = currency_symbols.get(transaction.sender.useraccount.preferred_currency, '')
        transaction.recipient_currency_symbol = currency_symbols.get(transaction.recipient.useraccount.preferred_currency, '')
        transaction.timestamp = transaction.timestamp.strftime('%B %d, %Y, %H:%M %p')

    # Prepare context data for the template
    context = {
        'user': request.user,
        'user_accounts': user_accounts,
        'transactions': transactions,
    }
    # Render the admin_home template with the context data
    return render(request, 'payapp/admin_home.html', context)

def logout_view(request):
    # Log out the user
    logout(request)
    # Redirect the user to the login page
    return redirect('login')