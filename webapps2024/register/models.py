from django.db import models
from django.contrib.auth.models import User


class UserAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    preferred_currency = models.CharField(max_length=3, choices=[('GBP', 'British Pound'), ('USD', 'US Dollar'), ('EUR', 'Euro')])
    is_activated = models.BooleanField(default=False)
    
    def __str__(self):
        return self.user.username

