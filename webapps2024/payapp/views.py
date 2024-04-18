from django.shortcuts import render
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import HttpResponse
import requests

def home_view(request):
    if not request.user.is_authenticated:
        return HttpResponse('Please login to view this page.', status=401)

    user_account = request.user.useraccount
    preferred_currency = user_account.preferred_currency
    base_balance_gbp = 1000.00  # Base balance in GBP

    if preferred_currency == 'GBP':
        converted_balance = base_balance_gbp
    else:
        api_url = f'http://localhost:8000/api/conversion/GBP/{preferred_currency}/{base_balance_gbp}'
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                result = response.json()
                converted_balance = result['converted_amount']
            else:
                return HttpResponse('Failed to fetch currency conversion data.', status=500)
        except Exception as e:
            return HttpResponse(f'An error occurred: {str(e)}', status=500)

    context = {
        'user': request.user,
        'balance': converted_balance,
        'currency': preferred_currency
    }
    return render(request, 'payapp/home.html', context)

def logout_view(request):
    logout(request)
    return redirect('login') 
