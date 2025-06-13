from django.urls import path
from .views import tds_virtual_ta

urlpatterns = [
    path('', tds_virtual_ta),
]
