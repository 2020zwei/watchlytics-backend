"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.generic import RedirectView


schema_view = get_schema_view(
    openapi.Info(
        title="Watch Trading Platform API",
        default_version='v1',
        description="API for Watch Trading Platform",
        terms_of_service="https://www.watchtradingplatform.com/terms/",
        contact=openapi.Contact(email="contact@watchtradingplatform.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/auth/', include('auth_.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/v1/inventory/', include('inventory.urls')),
    path('api/v1/', include('transactions.urls')),
    path('api/v1/', include('customers.urls')),
    path('api/v1/', include('market_insights.urls')),
    path('api/', include('subscription.urls')),
    path('api/v1/', include('invoices.urls')),
    path('api/v1/reports/', include('report.urls')),
    path('api/v1/shipping/', include('shipping.urls')),
    path('api/v1/dashboard/', include('dashboard.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
        re_path(r'^media/(?P<path>.)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
