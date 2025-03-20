from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('invoices', views.InvoiceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # path('generate/<int:transaction_id>/', views.GenerateInvoiceView.as_view(), name='generate_invoice'),
    # path('download/<str:invoice_number>/', views.DownloadInvoiceView.as_view(), name='download_invoice'),
]
