from django.contrib import admin
from .models import Transaction, PaymentRequest, Notification

admin.site.register(Transaction)
admin.site.register(PaymentRequest)
admin.site.register(Notification)