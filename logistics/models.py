from django.db import models
from django.contrib.auth.models import User

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class Hub(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    def __str__(self):
        return f"{self.name} ({self.city})"

class DriverApplication(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    vehicle = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Application: {self.full_name}"


class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100)

    phone = models.CharField(max_length=20)

    vehicle = models.CharField(max_length=100)

    city = models.CharField(max_length=100)

    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name


class Parcel(models.Model):

    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('AT_HUB', 'At Hub'),
        ('DELIVERED', 'Delivered'),
        ('REFUSED', 'Refused'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PAID', 'Paid'),
        ('REFUSED', 'Refused'),
    ]

    tracking_number = models.CharField(max_length=50, unique=True)

    sender_name = models.CharField(max_length=100)

    receiver_name = models.CharField(max_length=100)

    receiver_phone = models.CharField(max_length=20)

    delivery_address = models.CharField(max_length=255)

    departure_city = models.CharField(max_length=100)

    destination_city = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    weight = models.DecimalField(max_digits=10, decimal_places=2)

    note = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='CREATED'
    )

    is_cod_paid = models.BooleanField(default=False)

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID'
    )

    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    current_hub = models.ForeignKey(
        Hub,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    cod_credited_to_wallet = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.tracking_number

    def save(self, *args, **kwargs):
        if self.status == 'DELIVERED' and (self.payment_status == 'PAID' or self.is_cod_paid):
            self.payment_status = 'PAID'
            self.is_cod_paid = True
        elif self.status == 'REFUSED':
            self.payment_status = 'REFUSED'
            self.is_cod_paid = False

        super().save(*args, **kwargs)

        if self.status == 'DELIVERED' and self.is_cod_paid and not self.cod_credited_to_wallet and self.driver:
            wallet, created = DriverWallet.objects.get_or_create(driver=self.driver)
            wallet.balance += self.amount
            wallet.save()
            WalletTransaction.objects.create(
                wallet=wallet,
                parcel=self,
                transaction_type='COD_COLLECTION',
                amount=self.amount
            )
            # Use update to avoid infinite recursion
            Parcel.objects.filter(id=self.id).update(cod_credited_to_wallet=True)
            self.cod_credited_to_wallet = True


class ParcelStatus(models.Model):

    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name='statuses'
    )

    status = models.CharField(max_length=50)

    timestamp = models.DateTimeField(auto_now_add=True)

    note = models.TextField(blank=True)

    actor_driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logged_statuses'
    )

    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logged_statuses'
    )

    def __str__(self):
        return f"{self.parcel.tracking_number} - {self.status}"


class DriverWallet(models.Model):
    driver = models.OneToOneField(
        Driver,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    def __str__(self):
        return f"{self.driver.full_name}'s Wallet - {self.balance} DH"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('COD_COLLECTION', 'COD Collection'),
        ('PAYOUT', 'Payout / Cash Drop'),
    ]

    wallet = models.ForeignKey(
        DriverWallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} DH ({self.timestamp})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    language = models.CharField(max_length=20, default='English')
    notify_new_package = models.BooleanField(default=True)
    notify_status_update = models.BooleanField(default=True)
    notify_payment = models.BooleanField(default=True)
    
    company_name = models.CharField(max_length=100, default='Abrago')
    job_title = models.CharField(max_length=50, blank=True, null=True, choices=[('admin', 'Admin'), ('driver', 'Driver'), ('developer', 'Developer')])
    badge_number = models.CharField(max_length=50, blank=True, null=True)
    start_of_day = models.CharField(max_length=5, blank=True, null=True)
    end_of_day = models.CharField(max_length=5, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"

class CompanySettings(models.Model):
    # Singleton model
    company_name = models.CharField(max_length=100, default='AbraGo Logistics')
    contact_email = models.EmailField(default='contact@abrago.ma')
    support_phone = models.CharField(max_length=20, default='+212 600-000-000')
    address = models.TextField(default='Casablanca, Morocco')
    tax_id = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.company_name

class DeliveryZone(models.Model):
    name = models.CharField(max_length=100)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
