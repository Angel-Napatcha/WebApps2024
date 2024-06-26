from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Transaction(models.Model):
    # ForeignKey relationships to the User model
    sender = models.ForeignKey(User, related_name='sent_transactions', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_transactions', on_delete=models.CASCADE)
    
    # Other fields
    amount_sent = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Initially blank
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=[('Pending', 'Pending'), ('Successful', 'Successful'), ('Failed', 'Failed')])

    @property
    def currency_sent(self):
        return self.sender.useraccount.preferred_currency

    @property
    def currency_received(self):
        return self.recipient.useraccount.preferred_currency

    def save(self, *args, **kwargs):
        super(Transaction, self).save(*args, **kwargs)

    # String representation 
    def __str__(self):
        return f"{self.amount_sent} {self.currency_sent} from {self.sender.username} to {self.recipient.username} as {self.amount_received} {self.currency_received} ({self.status}) on {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    
class PaymentRequest(models.Model):
    # ForeignKey relations to handle requests and recipients
    requester = models.ForeignKey(User, related_name='outgoing_payment_requests', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='incoming_payment_requests', on_delete=models.CASCADE)
    
    # ForeignKey to the Transaction model
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_requests')
    
    # Other fields
    amount_requested = models.DecimalField(max_digits=10, decimal_places=2)
    amount_in_recipient_currency = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Field to store converted amount
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=15, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending')
    message = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):      
        super(PaymentRequest, self).save(*args, **kwargs)
        
    # String representation 
    def __str__(self):
        return f"Request by {self.requester.username} to {self.recipient.username} for {self.amount_requested} {self.requester.useraccount.preferred_currency} - {self.amount_in_recipient_currency} {self.recipient.useraccount.preferred_currency} ({self.status}) on {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
  
    
class Notification(models.Model):
    # ForeignKey relationship to User model
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    # Other fields
    message = models.TextField()
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)

    # String representation
    def __str__(self):
        return f'Notification for {self.recipient.username} - Read: {self.read}'