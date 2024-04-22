import requests
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from decimal import Decimal

# Hardcoded exchange rates
EXCHANGE_RATES = {
    'GBP': {'USD': 1.24, 'EUR': 1.17},
    'USD': {'GBP': 0.8, 'EUR': 0.94},
    'EUR': {'GBP': 0.86, 'USD': 1.07},
}

def construct_api(request, from_currency, to_currency, amount):
    try:
        amount = float(amount)
        rates = EXCHANGE_RATES.get(from_currency, {})
        if to_currency in rates:
            rate = rates[to_currency]
            converted_amount = amount * rate
            return JsonResponse({
                'original_amount': amount,
                'original_currency': from_currency,
                'converted_currency': to_currency,
                'converted_amount': converted_amount,
                'rate': rate
            })
        else:
            return JsonResponse({'error': 'Currency conversion not supported between these currencies.'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid amount provided.'}, status=400)
    except KeyError:
        return JsonResponse({'error': 'Unsupported currency provided.'}, status=404)

def convert_currency(from_currency, to_currency, amount):
    api_url = f"http://localhost:8000/api/conversion/{from_currency}/{to_currency}/{amount}/"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return Decimal(data['converted_amount'])
        else:
            raise ValidationError(f"Currency conversion failed with status code: {response.status_code}")
    except requests.RequestException as e:
        raise ValidationError(f"Failed to connect to currency conversion service: {str(e)}")