from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from currency_converter_api.views import convert_currency

class Transaction(models.Model):
    sender = models.ForeignKey(User, related_name='sent_transactions', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_transactions', on_delete=models.CASCADE)
    amount_sent = models.DecimalField(max_digits=10, decimal_places=2)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Initially blank
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, default='Completed', choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Failed', 'Failed')])

    @property
    def currency_sent(self):
        return self.sender.useraccount.preferred_currency

    @property
    def currency_received(self):
        return self.recipient.useraccount.preferred_currency

    def save(self, *args, **kwargs):
        if not self.amount_received:  # Check if the conversion is needed
            if self.currency_sent != self.currency_received:
                self.amount_received = convert_currency(self.currency_sent, self.currency_received, self.amount_sent)
            else:
                self.amount_received = self.amount_sent
        super(Transaction, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount_sent} {self.currency_sent} from {self.sender.username} to {self.recipient.username} as {self.amount_received} {self.currency_received} on {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"