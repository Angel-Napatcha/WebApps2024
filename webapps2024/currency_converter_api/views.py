from django.shortcuts import render
from django.http import JsonResponse

# Hardcoded exchange rates
EXCHANGE_RATES = {
    'GBP': {'USD': 1.24, 'EUR': 1.17},
    'USD': {'GBP': 0.8, 'EUR': 0.94},
    'EUR': {'GBP': 0.86, 'USD': 1.07},
}

def convert_currency(request, currency1, currency2, amount):
    try:
        amount = float(amount)
        rates = EXCHANGE_RATES.get(currency1, {})
        if currency2 in rates:
            rate = rates[currency2]
            converted_amount = amount * rate
            return JsonResponse({
                'original_amount': amount,
                'original_currency': currency1,
                'converted_currency': currency2,
                'converted_amount': converted_amount,
                'rate': rate
            })
        else:
            return JsonResponse({'error': 'Currency conversion not supported between these currencies.'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid amount provided.'}, status=400)
    except KeyError:
        return JsonResponse({'error': 'Unsupported currency provided.'}, status=404)

