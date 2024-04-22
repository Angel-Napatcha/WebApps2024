from django.contrib import admin
from django.urls import path
from register.views import register_view, activate, login_view, verify_account
from currency_converter_api.views import construct_api
from payapp.views import home_view, transaction_view, transaction_complete_view, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webapps2024/register/', register_view, name='register'),
    path('webapps2024/verification/', verify_account, name='account_verification'), 
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('webapps2024/register/login/', login_view, name='login'),
    path('api/conversion/<str:from_currency>/<str:to_currency>/<str:amount>/', construct_api, name='currency_converter'),
    path('webapps2024/payapp/home/', home_view, name='home'),
    path('webapps2024/payapp/home/transaction', transaction_view, name='transaction'),
    path('webapps2024/payapp/home/transaction_complete', transaction_complete_view, name='transaction_complete'),
    path('webapps2024/payapp/logout/', logout_view, name='logout')
]
