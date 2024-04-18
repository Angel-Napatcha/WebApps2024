"""
URL configuration for webapps2024 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from register.views import register_view, activate, login_view, account_verification
from currency_converter_api.views import convert_currency
from payapp.views import home_view, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webapps2024/register/', register_view, name='register'),
    path('webapps2024/verification/', account_verification, name='account_verification'), 
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('webapps2024/register/login/', login_view, name='login'),
    path('api/conversion/<str:currency1>/<str:currency2>/<str:amount>/', convert_currency, name='convert_currency'),
    path('webapps2024/payapp/home/', home_view, name='home'),
    path('webapps2024/payapp/logout/', logout_view, name='logout')
]
