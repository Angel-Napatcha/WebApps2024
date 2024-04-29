from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.test import Client
from decimal import Decimal

# Hardcoded exchange rates
EXCHANGE_RATES = {
    'GBP': {'USD': 1.24, 'EUR': 1.17},
    'USD': {'GBP': 0.8, 'EUR': 0.94},
    'EUR': {'GBP': 0.86, 'USD': 1.07},
}

class CurrencyConversionSerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    amount = serializers.FloatField()

    def validate(self, attrs):
        valid_currencies = ['GBP', 'USD', 'EUR']
        if attrs['from_currency'] not in valid_currencies or attrs['to_currency'] not in valid_currencies:
            raise serializers.ValidationError("Unsupported currency.")
        return attrs

    def create(self, validated_data):
        from_currency = validated_data['from_currency']
        to_currency = validated_data['to_currency']
        amount = validated_data['amount']
        rate = EXCHANGE_RATES[from_currency][to_currency]
        converted_amount = amount * rate
        return {
            'original_amount': amount,
            'original_currency': from_currency,
            'converted_currency': to_currency,
            'converted_amount': converted_amount,
            'rate': rate
        }

class CurrencyConversionAPI(APIView):
    def get(self, request, from_currency, to_currency, amount):
        serializer = CurrencyConversionSerializer(data={
            'from_currency': from_currency,
            'to_currency': to_currency,
            'amount': amount
        })
        if serializer.is_valid():
            result = serializer.create(serializer.validated_data)
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def convert_currency(from_currency, to_currency, amount):
    client = Client()
    response = client.get(f'/conversion/{from_currency}/{to_currency}/{amount}/')
    if response.status_code == 200:
        data = response.json()
        converted_amount = Decimal(data['converted_amount'])
        return  converted_amount
    else:
        raise Exception(f"API call failed with status {response.status_code}: {response.content}")