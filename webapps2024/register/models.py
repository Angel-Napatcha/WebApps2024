from django.db import models
from django.contrib.auth.models import User
import requests
from django.core.exceptions import ValidationError


class UserAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    preferred_currency = models.CharField(max_length=3, choices=[('GBP', 'British Pound'), ('USD', 'US Dollar'), ('EUR', 'Euro')])
    is_activated = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    def save(self, *args, **kwargs):
        if not self.pk:
            default_balance_gbp = 1000.00
            if self.preferred_currency == 'GBP':
                # If the preferred currency is GBP, use the default balance directly
                self.balance = default_balance_gbp
            else:
                # Construct the URL for the currency conversion API
                api_url = f"http://localhost:8000/api/conversion/GBP/{self.preferred_currency}/{default_balance_gbp}/"
                try:
                    response = requests.get(api_url)
                    if response.status_code == 200:
                        data = response.json()
                        self.balance = data['converted_amount']
                    else:
                        raise ValidationError("Currency conversion failed with status code: {}".format(response.status_code))
                except requests.RequestException as e:
                    raise ValidationError("Failed to connect to currency conversion service: {}".format(str(e)))

        super(UserAccount, self).save(*args, **kwargs)