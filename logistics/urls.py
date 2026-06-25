from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('portal/', views.home, name='home'),
    path('tracking/', views.tracking, name='tracking'),
    path('invoice/<str:tracking_number>/', views.invoice, name='invoice'),
    path('driver/login/', views.driver_login, name='driver_login'),
    path('driver/dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('driver/logout/', views.driver_logout, name='driver_logout'),
    path('driver/update_city/', views.driver_update_city, name='driver_update_city'),
    path('driver/update_status/<str:tracking_number>/', views.driver_update_status, name='driver_update_status'),
    path('api/track/<str:tracking_number>/', views.api_track_parcel, name='api_track_parcel'),
    path('api/wallet/', views.api_wallet_data, name='api_wallet_data'),
    path('api/update_status/<str:tracking_number>/', views.api_update_status, name='api_update_status'),
    path('api/delete_parcel/<str:tracking_number>/', views.api_delete_parcel, name='api_delete_parcel'),
    path('logout/', views.logout_view, name='logout'),
    path('api/auth/signup/', views.api_signup, name='api_signup'),
    path('api/auth/login/', views.api_login, name='api_login'),
    
    # Settings APIs
    path('api/settings/profile/', views.api_settings_profile, name='api_settings_profile'),
    path('api/settings/security/', views.api_settings_security, name='api_settings_security'),
    path('api/settings/company/', views.api_settings_company, name='api_settings_company'),
    path('api/settings/zones/', views.api_settings_zones, name='api_settings_zones'),
]