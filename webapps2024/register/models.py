from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from currency_converter_api.views import convert_currency


class UserAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_currency = models.CharField(max_length=3, choices=[('GBP', 'British Pound'), ('USD', 'US Dollar'), ('EUR', 'Euro')])
    is_activated = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        if not self.pk:
            default_balance_gbp = 1000.00
            if self.preferred_currency == 'GBP':
                self.balance = default_balance_gbp
            else:
                try:
                    # Use the utility function to convert currency
                    self.balance = convert_currency('GBP', self.preferred_currency, default_balance_gbp)
                except ValidationError as e:
                    raise ValidationError(f"Currency conversion error: {e}")

        super(UserAccount, self).save(*args, **kwargs)