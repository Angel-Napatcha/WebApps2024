from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from currency_converter_api.views import convert_currency


class UserAccount(models.Model):
    # Link to the Django User model, with a one-to-one relationship
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Other fields
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_currency = models.CharField(max_length=3, choices=[
        ('GBP', 'British Pound'), ('USD', 'US Dollar'), ('EUR', 'Euro')])
    is_activated = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        # Check if this is a new instance
        if not self.pk:
            # Default balance in GBP
            default_balance_gbp = 1000.00
            
            # If the preferred currency is GBP, set balance to the default value
            if self.preferred_currency == 'GBP':
                self.balance = default_balance_gbp
            else:
                try:
                    # Convert the default GBP balance to the preferred currency
                    self.balance = convert_currency('GBP', self.preferred_currency, default_balance_gbp)
                except ValidationError as e:
                    raise ValidationError(f"Currency conversion error: {e}")

        # Call the save method after handling the custom logic
        super(UserAccount, self).save(*args, **kwargs)