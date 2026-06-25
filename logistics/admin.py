from django.contrib import admin
from .models import Driver, Parcel, ParcelStatus, DriverWallet, WalletTransaction


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'vehicle', 'city', 'is_available')
    list_filter = ('city', 'is_available')
    search_fields = ('full_name', 'phone')


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ('tracking_number', 'sender_name', 'receiver_name', 'destination_city', 'amount', 'status', 'is_cod_paid', 'driver')
    list_filter = ('status', 'is_cod_paid', 'departure_city', 'destination_city')
    search_fields = ('tracking_number', 'sender_name', 'receiver_name')


@admin.register(ParcelStatus)
class ParcelStatusAdmin(admin.ModelAdmin):
    list_display = ('parcel', 'status', 'timestamp', 'note')
    list_filter = ('status', 'timestamp')
    search_fields = ('parcel__tracking_number', 'status')


@admin.register(DriverWallet)
class DriverWalletAdmin(admin.ModelAdmin):
    list_display = ('driver', 'balance')
    search_fields = ('driver__full_name',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'parcel', 'transaction_type', 'amount', 'timestamp')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('wallet__driver__full_name', 'parcel__tracking_number')