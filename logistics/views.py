import os
import json
from django.core.mail import send_mail
import qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.urls import reverse
from django.db.models import Count, Q, Sum
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Parcel, ParcelStatus, Driver, DriverWallet, WalletTransaction, City, DriverApplication, Hub

# -----------------------------------------------------------------------------
# PAGE D'ACCUEIL & FONCTIONNALITÉS PUBLIQUES
# -----------------------------------------------------------------------------
def landing_page(request):
    """
    Gère la page d'accueil publique.
    Inclut la logique du formulaire de candidature des chauffeurs (création et notification par e-mail).
    """
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        city = request.POST.get('city')
        vehicle = request.POST.get('vehicle')
        
        if full_name and email and phone:
            DriverApplication.objects.create(
                full_name=full_name,
                email=email,
                phone=phone,
                city=city,
                vehicle=vehicle
            )
            
            # Send Email Notification
            try:
                subject = f"New Driver Application: {full_name}"
                message = f"You have a new driver application!\n\nName: {full_name}\nEmail: {email}\nPhone: {phone}\nCity: {city}\nVehicle: {vehicle}"
                send_mail(
                    subject,
                    message,
                    'abrareyaktine@gmail.com', # From email
                    ['abrareyaktine@gmail.com'], # To email
                    fail_silently=True, # Will silently fail if password is not configured yet, preventing a crash
                )
            except Exception as e:
                pass
                
            messages.success(request, "Your application has been received! We will contact you soon.")
        else:
            messages.error(request, "Please fill out all required fields.")
            
        return redirect('landing_page')
        
    context = {
        'cities': City.objects.all().order_by('name')
    }
    return render(request, "landing_page.html", context)


# -----------------------------------------------------------------------------
# TABLEAU DE BORD ADMIN & GESTION DES COLIS
# -----------------------------------------------------------------------------
def home(request):
    """
    Vue du tableau de bord Admin.
    Responsable de :
    - L'affichage des statistiques (revenus, statuts des colis, etc.)
    - La création de nouveaux colis
    - La génération automatique de QR Codes
    - L'assignation automatique des colis aux chauffeurs selon la charge de travail
    """
    created_parcel = None
    qr_code_url = None
    success = False

    if request.method == "POST":
        edit_tracking = request.POST.get("edit_tracking")
        sender_name = request.POST.get("sender_name")
        receiver_name = request.POST.get("receiver_name")
        receiver_phone = request.POST.get("receiver_phone")
        delivery_address = request.POST.get("delivery_address")
        departure_city = request.POST.get("departure_city")
        destination_city = request.POST.get("destination_city")
        amount_raw = request.POST.get("amount")
        weight_raw = request.POST.get("weight")
        note = request.POST.get("note", "")

        # Default values if fields are empty
        amount = float(amount_raw) if amount_raw else 0.0
        weight = float(weight_raw) if weight_raw else 0.0

        if edit_tracking:
            parcel = get_object_or_404(Parcel, tracking_number=edit_tracking)
            parcel.sender_name = sender_name
            parcel.receiver_name = receiver_name
            parcel.receiver_phone = receiver_phone
            parcel.delivery_address = delivery_address
            parcel.departure_city = departure_city
            parcel.destination_city = destination_city
            parcel.amount = amount
            parcel.weight = weight
            parcel.note = note
            parcel.save()

            actor_user = request.user if request.user.is_authenticated else None
            ParcelStatus.objects.create(
                parcel=parcel,
                status=parcel.status,
                note=f"Parcel details updated by staff.",
                actor_user=actor_user
            )
            messages.success(request, f"Parcel {parcel.tracking_number} updated successfully!")
            created_parcel = parcel
            qr_code_url = f"{settings.STATIC_URL}qr_codes/{parcel.tracking_number}.png"
            success = True
        else:
            # FONCTIONNALITÉ : Génération de numéro de suivi unique
            # Génère un ID de suivi unique comme ABR1, ABR2, etc.
            count = Parcel.objects.count()
            tracking_number = "ABR" + str(count + 1)
            while Parcel.objects.filter(tracking_number=tracking_number).exists():
                count += 1
                tracking_number = "ABR" + str(count + 1)

            # FONCTIONNALITÉ : Algorithme d'assignation automatique
            # Trouve automatiquement les chauffeurs disponibles dans la ville de départ
            # et assigne le colis au chauffeur ayant le moins de colis actifs.
            available_drivers = Driver.objects.filter(is_available=True, city__iexact=departure_city)
            assigned_driver = None
            if available_drivers.exists():
                # Assign the driver with the fewest active parcels
                assigned_driver = available_drivers.annotate(
                    active_parcels=Count('parcel', filter=~Q(parcel__status='DELIVERED'))
                ).order_by('active_parcels').first()
            else:
                # Fallback to any available driver in the system
                all_available = Driver.objects.filter(is_available=True)
                if all_available.exists():
                    assigned_driver = all_available.first()

            # Create the parcel
            parcel = Parcel.objects.create(
                tracking_number=tracking_number,
                sender_name=sender_name,
                receiver_name=receiver_name,
                receiver_phone=receiver_phone,
                delivery_address=delivery_address,
                departure_city=departure_city,
                destination_city=destination_city,
                amount=amount,
                weight=weight,
                note=note,
                driver=assigned_driver,
                status='CREATED',
                payment_status='UNPAID'
            )

            # Log initial status with actor operator (User)
            actor_user = request.user if request.user.is_authenticated else None
            ParcelStatus.objects.create(
                parcel=parcel,
                status="CREATED",
                note="Parcel created in system.",
                actor_user=actor_user
            )

            # FONCTIONNALITÉ : Génération de QR Code
            # Génère un code QR dynamique contenant l'URL de suivi du colis
            tracking_url = request.build_absolute_uri(reverse('tracking')) + f"?tracking_number={tracking_number}"
            qr = qrcode.make(tracking_url)

            # Save the QR code image
            qr_folder = os.path.join(settings.BASE_DIR, "static", "qr_codes")
            os.makedirs(qr_folder, exist_ok=True)
            qr_path = os.path.join(qr_folder, f"{tracking_number}.png")
            qr.save(qr_path)

            messages.success(request, f"Parcel {tracking_number} created successfully!")
            created_parcel = parcel
            qr_code_url = f"{settings.STATIC_URL}qr_codes/{tracking_number}.png"
            success = True

    # Calculate statistics and context for home page (both GET and POST)
    total_packages_count = Parcel.objects.count()
    delivered_packages_count = Parcel.objects.filter(status='DELIVERED').count()
    pending_packages_count = Parcel.objects.exclude(status__in=['DELIVERED', 'REFUSED']).count()
    total_revenue = Parcel.objects.filter(Q(is_cod_paid=True) | Q(payment_status='PAID')).aggregate(total=Sum('amount'))['total'] or 0.00
    paid_invoices_count = Parcel.objects.filter(Q(is_cod_paid=True) | Q(payment_status='PAID')).count()
    pending_invoices_count = Parcel.objects.exclude(Q(is_cod_paid=True) | Q(payment_status='PAID')).exclude(payment_status='REFUSED').count()

    # Delivery Status counts
    in_transit_count = Parcel.objects.filter(status='IN_TRANSIT').count()
    picked_up_count = Parcel.objects.filter(status='PICKED_UP').count()
    created_count = Parcel.objects.filter(status='CREATED').count()
    refused_count = Parcel.objects.filter(status='REFUSED').count()

    # Calculate percentages for the UI charts
    delivered_pct = int((delivered_packages_count / total_packages_count) * 100) if total_packages_count > 0 else 0
    in_transit_pct = int(((in_transit_count + picked_up_count) / total_packages_count) * 100) if total_packages_count > 0 else 0
    pending_pct = int((created_count / total_packages_count) * 100) if total_packages_count > 0 else 0
    refused_pct = int((refused_count / total_packages_count) * 100) if total_packages_count > 0 else 0

    # Hub Package Tracker
    hub_stats = Parcel.objects.filter(status='AT_HUB', current_hub__isnull=False).values('current_hub__name').annotate(count=Count('id')).order_by('-count')[:4]

    # Driver Availability stats
    drivers_en_tournee = Driver.objects.filter(parcel__status__in=['CREATED', 'PICKED_UP', 'IN_TRANSIT']).distinct().count()
    drivers_en_pause = Driver.objects.filter(is_available=True).exclude(parcel__status__in=['CREATED', 'PICKED_UP', 'IN_TRANSIT']).distinct().count()
    drivers_hors_ligne = Driver.objects.filter(is_available=False).exclude(parcel__status__in=['CREATED', 'PICKED_UP', 'IN_TRANSIT']).distinct().count()
    total_drivers = Driver.objects.count()

    en_tournee_pct = int((drivers_en_tournee / total_drivers) * 100) if total_drivers > 0 else 0
    en_pause_pct = int((drivers_en_pause / total_drivers) * 100) if total_drivers > 0 else 0
    hors_ligne_pct = int((drivers_hors_ligne / total_drivers) * 100) if total_drivers > 0 else 0

    # Time Tracking (Packages currently PICKED_UP)
    picked_up_parcels = Parcel.objects.filter(status='PICKED_UP').select_related('driver').order_by('updated_at')[:4]

    # Recent activity logs from ParcelStatus
    recent_activities = ParcelStatus.objects.select_related('parcel', 'actor_driver', 'actor_user').order_by('-timestamp')[:5]

    recent_parcels = Parcel.objects.select_related('driver', 'current_hub').order_by('-created_at')[:5]
    all_parcels = Parcel.objects.select_related('driver', 'current_hub').order_by('-created_at')

    context = {
        # Create form status
        "success": success,
        "created_parcel": created_parcel,
        "qr_code_url": qr_code_url,

        # Stats
        "total_packages_count": total_packages_count,
        "delivered_packages_count": delivered_packages_count,
        "pending_packages_count": pending_packages_count,
        "total_revenue": total_revenue,
        "paid_invoices_count": paid_invoices_count,
        "pending_invoices_count": pending_invoices_count,

        # Delivery status chart details
        "delivered_count": delivered_packages_count,
        "in_transit_count": in_transit_count + picked_up_count,
        "pending_count": created_count,
        "refused_count": refused_count,

        "delivered_pct": delivered_pct,
        "in_transit_pct": in_transit_pct,
        "pending_pct": pending_pct,
        "refused_pct": refused_pct,

        # Hub stats
        "hub_stats": hub_stats,

        # Time tracking
        "picked_up_parcels": picked_up_parcels,

        # Driver availability
        "drivers_en_tournee": drivers_en_tournee,
        "drivers_en_pause": drivers_en_pause,
        "drivers_hors_ligne": drivers_hors_ligne,
        "en_tournee_pct": en_tournee_pct,
        "en_pause_pct": en_pause_pct,
        "hors_ligne_pct": hors_ligne_pct,

        # Routes & Activity
        "recent_activities": recent_activities,

        # Parcel lists
        "recent_parcels": recent_parcels,
        "all_parcels": all_parcels,
        "cities": City.objects.all().order_by('name'),
        "hubs": Hub.objects.all().order_by('name'),
        "drivers_list": Driver.objects.select_related('user').prefetch_related('parcel_set').all().order_by('full_name'),
    }

    return render(request, "home.html", context)


# -----------------------------------------------------------------------------
# SYSTÈME DE SUIVI PUBLIC
# -----------------------------------------------------------------------------
def tracking(request):
    """
    Vue de suivi public. Permet à quiconque de suivre un colis via son numéro.
    Affiche l'historique complet et détaillé du trajet.
    """
    parcel = None
    statuses = None
    current_status = None
    tracking_number = request.POST.get("tracking_number") or request.GET.get("tracking_number")

    if tracking_number:
        tracking_number = tracking_number.strip()
        try:
            parcel = Parcel.objects.select_related('driver', 'current_hub').get(tracking_number__iexact=tracking_number)
            statuses = ParcelStatus.objects.filter(parcel=parcel).select_related('actor_driver', 'actor_user').order_by("timestamp")
            last_status = statuses.last()
            if last_status:
                current_status = last_status.status
        except Parcel.DoesNotExist:
            messages.error(request, f"No parcel found with tracking number '{tracking_number}'.")

    return render(
        request,
        "tracking.html",
        {
            "parcel": parcel,
            "statuses": statuses,
            "current_status": current_status,
            "searched_number": tracking_number
        }
    )


# -----------------------------------------------------------------------------
# GÉNÉRATION / IMPRESSION DE FACTURE (INVOICE)
# -----------------------------------------------------------------------------
def invoice(request, tracking_number):
    """
    Génère une facture imprimable pour un colis.
    Inclut le QR Code pour un scan facile.
    Peut être imprimée ou sauvegardée en PDF via Ctrl+P.
    """
    parcel = get_object_or_404(Parcel, tracking_number__iexact=tracking_number)
    # Check if QR Code exists, generate if missing
    qr_folder = os.path.join(settings.BASE_DIR, "static", "qr_codes")
    qr_path = os.path.join(qr_folder, f"{parcel.tracking_number}.png")
    if not os.path.exists(qr_path):
        os.makedirs(qr_folder, exist_ok=True)
        tracking_url = request.build_absolute_uri(reverse('tracking')) + f"?tracking_number={parcel.tracking_number}"
        qr = qrcode.make(tracking_url)
        qr.save(qr_path)

    return render(request, "invoice.html", {"parcel": parcel})


from django.contrib.auth import authenticate, login

def driver_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if hasattr(user, 'driver'):
                request.session['driver_id'] = user.driver.id
                messages.success(request, f"Logged in as {user.driver.full_name}")
                return redirect('driver_dashboard')
            else:
                messages.error(request, "This account is not a driver account.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "driver_login.html")


def driver_dashboard(request):
    driver_id = request.session.get('driver_id')
    if not driver_id:
        messages.warning(request, "Please log in first.")
        return redirect('driver_login')

    driver = get_object_or_404(Driver, id=driver_id)
    wallet, created = DriverWallet.objects.get_or_create(driver=driver)
    transactions = wallet.transactions.all().order_by('-timestamp')
    active_parcels = Parcel.objects.filter(driver=driver).exclude(status='DELIVERED').exclude(status='REFUSED').order_by('-created_at')
    completed_parcels = Parcel.objects.filter(driver=driver, status__in=['DELIVERED', 'REFUSED']).order_by('-updated_at')

    # Available status choices for the driver select dropdown
    status_choices = [
        ('PICKED_UP', 'Picked Up'),
        ('IN_TRANSIT', 'In Transit'),
        ('AT_HUB', 'Drop at Stocking Hub'),
        ('DELIVERED', 'Delivered'),
        ('REFUSED', 'Refused / Colis Refusé'),
    ]

    return render(request, "driver_dashboard.html", {
        "driver": driver,
        "wallet": wallet,
        "transactions": transactions,
        "active_parcels": active_parcels,
        "completed_parcels": completed_parcels,
        "status_choices": status_choices,
        "cities": City.objects.all().order_by('name'),
        "hubs": Hub.objects.filter(city__iexact=driver.city)
    })

def driver_logout(request):
    if 'driver_id' in request.session:
        del request.session['driver_id']
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    messages.success(request, "Logged out securely.")
    return redirect('driver_login')

def driver_update_city(request):
    driver_id = request.session.get('driver_id')
    if not driver_id:
        return redirect('driver_login')

    if request.method == "POST":
        new_city = request.POST.get('city')
        if new_city:
            driver = get_object_or_404(Driver, id=driver_id)
            driver.city = new_city.strip()
            driver.save()
            messages.success(request, f"Location updated to {driver.city}")
            
    return redirect('driver_dashboard')


# -----------------------------------------------------------------------------
# ACTIONS CHAUFFEUR & LOGIQUE LOGISTIQUE
# -----------------------------------------------------------------------------
def driver_update_status(request, tracking_number):
    """
    Logique centrale pour les mises à jour de statut par les chauffeurs.
    Gère :
    - Les mises à jour normales (Récupéré, En route, Livré)
    - La logique de paiement à la livraison (COD)
    - Les dépôts en Hub (relais) et la réassignation automatique
    """
    driver_id = request.session.get('driver_id')
    if not driver_id:
        return redirect('driver_login')

    driver = get_object_or_404(Driver, id=driver_id)
    parcel = get_object_or_404(Parcel, tracking_number__iexact=tracking_number, driver=driver)

    if request.method == "POST":
        new_status = request.POST.get("status")
        is_cod_paid = request.POST.get("is_cod_paid") == "on"
        note = request.POST.get("note", "").strip()

        if new_status:
            parcel.status = new_status
            if is_cod_paid or new_status == 'DELIVERED':
                # Force cod paid to true if confirmed or delivered
                parcel.is_cod_paid = True
                parcel.payment_status = 'PAID'
                
                # Update driver's location to the destination city
                driver.city = parcel.destination_city
                driver.save()
            elif new_status == 'REFUSED':
                parcel.is_cod_paid = False
                parcel.payment_status = 'REFUSED'
                
                # Update driver's location to the destination city
                driver.city = parcel.destination_city
                driver.save()
            elif new_status == 'AT_HUB':
                # FONCTIONNALITÉ : Dépôt en Hub & Réassignation Intelligente
                # Si un chauffeur dépose un colis dans un Hub, il est désassigné.
                # Le système l'assigne alors automatiquement à un autre chauffeur 
                # de la ville du Hub qui se dirige vers la destination finale.
                hub_id = request.POST.get('hub_id')
                if hub_id:
                    from .models import Hub
                    hub = Hub.objects.get(id=hub_id)
                    parcel.current_hub = hub
                    parcel.driver = None
                    parcel.departure_city = hub.city
                    
                    # Update driver's location to the hub city
                    driver.city = hub.city
                    driver.save()
                    
                    # Auto-assign logic
                    available_drivers = Driver.objects.filter(is_available=True, city__iexact=hub.city)
                    if driver:
                        available_drivers = available_drivers.exclude(id=driver.id)
                        
                    if available_drivers.exists():
                        from django.db.models import Count
                        perfect_match = available_drivers.filter(
                            parcel__destination_city__iexact=parcel.destination_city,
                            parcel__status__in=['PICKED_UP', 'IN_TRANSIT']
                        ).annotate(parcel_count=Count('parcel')).order_by('parcel_count').first()
                        
                        if perfect_match:
                            assigned_driver = perfect_match
                            note = f"Dropped at Hub {hub.name}. Smart-assigned to {assigned_driver.full_name} (heading to {parcel.destination_city})"
                        else:
                            assigned_driver = available_drivers.annotate(parcel_count=Count('parcel')).order_by('parcel_count').first()
                            note = f"Dropped at Hub {hub.name}. Auto-assigned to {assigned_driver.full_name}"
                            
                        parcel.driver = assigned_driver
                    else:
                        note = f"Dropped at Hub {hub.name}. Waiting for driver."
            
            parcel.save()

            ParcelStatus.objects.create(
                parcel=parcel,
                status=new_status,
                note=note or f"Status updated to {new_status} by driver {driver.full_name}",
                actor_driver=driver
            )
            messages.success(request, f"Updated parcel {tracking_number} status to {new_status}!")
        else:
            messages.error(request, "Invalid status selected.")

    return redirect('driver_dashboard')


@csrf_exempt
def api_track_parcel(request, tracking_number):
    try:
        parcel = Parcel.objects.select_related('driver', 'current_hub').get(tracking_number__iexact=tracking_number.strip())
        statuses = ParcelStatus.objects.filter(parcel=parcel).select_related('actor_driver', 'actor_user').order_by('timestamp')
        
        status_history = []
        for s in statuses:
            actor = "System"
            if s.actor_driver:
                actor = f"Driver {s.actor_driver.full_name}"
            elif s.actor_user:
                actor = f"Staff ({s.actor_user.username})"
                
            status_history.append({
                'status': s.status,
                'timestamp': s.timestamp.strftime('%d %b %Y — %H:%M'),
                'note': s.note,
                'actor': actor
            })
            
        data = {
            'tracking_number': parcel.tracking_number,
            'sender_name': parcel.sender_name,
            'receiver_name': parcel.receiver_name,
            'receiver_phone': parcel.receiver_phone,
            'delivery_address': parcel.delivery_address,
            'departure_city': parcel.departure_city,
            'destination_city': parcel.destination_city,
            'amount': float(parcel.amount),
            'weight': float(parcel.weight),
            'status': parcel.get_status_display(),
            'payment_status': parcel.get_payment_status_display(),
            'current_hub': parcel.current_hub.name if parcel.current_hub else '-',
            'driver_name': parcel.driver.full_name if parcel.driver else 'Not Assigned',
            'driver_phone': parcel.driver.phone if parcel.driver else '',
            'history': status_history
        }
        return JsonResponse({'success': True, 'data': data})
    except Parcel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Parcel not found'})


@csrf_exempt
def api_update_status(request, tracking_number):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            is_cod_paid = data.get('is_cod_paid', False)
            note = data.get('note', '')
        except Exception:
            new_status = request.POST.get('status')
            is_cod_paid = request.POST.get('is_cod_paid') == 'true' or request.POST.get('is_cod_paid') == 'on'
            note = request.POST.get('note', '')

        parcel = get_object_or_404(Parcel, tracking_number__iexact=tracking_number)
        if new_status:
            parcel.status = new_status
            if new_status == 'DELIVERED':
                if parcel.amount > 0:
                    parcel.is_cod_paid = is_cod_paid
                    parcel.payment_status = 'PAID' if is_cod_paid else 'UNPAID'
                else:
                    parcel.is_cod_paid = True
                    parcel.payment_status = 'PAID'
                
                if parcel.driver:
                    parcel.driver.city = parcel.destination_city
                    parcel.driver.save()
            elif new_status == 'REFUSED':
                parcel.is_cod_paid = False
                parcel.payment_status = 'REFUSED'
                
                if parcel.driver:
                    parcel.driver.city = parcel.destination_city
                    parcel.driver.save()
            elif new_status == 'AT_HUB':
                hub_id = data.get('hub_id') if isinstance(data, dict) else request.POST.get('hub_id')
                if hub_id:
                    from .models import Hub
                    hub = Hub.objects.get(id=hub_id)
                    parcel.current_hub = hub
                    old_driver = parcel.driver
                    parcel.driver = None
                    parcel.departure_city = hub.city
                    
                    if old_driver:
                        old_driver.city = hub.city
                        old_driver.save()
                        
                    available_drivers = Driver.objects.filter(is_available=True, city__iexact=hub.city)
                    if old_driver:
                        available_drivers = available_drivers.exclude(id=old_driver.id)
                        
                    if available_drivers.exists():
                        from django.db.models import Count
                        perfect_match = available_drivers.filter(
                            parcel__destination_city__iexact=parcel.destination_city,
                            parcel__status__in=['PICKED_UP', 'IN_TRANSIT']
                        ).annotate(parcel_count=Count('parcel')).order_by('parcel_count').first()
                        
                        if perfect_match:
                            assigned_driver = perfect_match
                            note = f"Dropped at Hub {hub.name}. Smart-assigned to {assigned_driver.full_name}"
                        else:
                            assigned_driver = available_drivers.annotate(parcel_count=Count('parcel')).order_by('parcel_count').first()
                            note = f"Dropped at Hub {hub.name}. Auto-assigned to {assigned_driver.full_name}"
                        parcel.driver = assigned_driver
                    else:
                        note = f"Dropped at Hub {hub.name}. Waiting for driver."
            parcel.save()

            # Add history entry
            actor_driver = None
            actor_user = None

            # Determine actor
            driver_id = request.session.get('driver_id')
            if driver_id:
                try:
                    actor_driver = Driver.objects.get(id=driver_id)
                except Driver.DoesNotExist:
                    pass

            if not actor_driver and parcel.driver:
                actor_driver = parcel.driver

            if not actor_driver and request.user.is_authenticated:
                actor_user = request.user

            actor_label = "System"
            if actor_driver:
                actor_label = f"Driver {actor_driver.full_name}"
            elif actor_user:
                actor_label = f"Staff ({actor_user.username})"

            ParcelStatus.objects.create(
                parcel=parcel,
                status=new_status,
                note=note or f"Status updated to {new_status} by {actor_label}",
                actor_driver=actor_driver,
                actor_user=actor_user
            )
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'No status provided'})
    return JsonResponse({'success': False, 'error': 'POST method required'})


@csrf_exempt
def api_delete_parcel(request, tracking_number):
    if request.method == "POST" or request.method == "DELETE":
        parcel = get_object_or_404(Parcel, tracking_number__iexact=tracking_number)
        parcel.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'POST/DELETE method required'})


def logout_view(request):
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    messages.success(request, "Logged out successfully from session.")
    return redirect('home')


@csrf_exempt
def api_signup(request):
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'POST request required.'})
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not username or not password or not email:
            return JsonResponse({'success': False, 'error': 'All fields are required.'})

        from django.contrib.auth.models import User
        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists.'})
        
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already exists.'})

        user = User.objects.create_user(username=username, email=email, password=password)
        return JsonResponse({'success': True, 'message': 'Account created successfully!'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def api_login(request):
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'POST request required.'})
    try:
        data = json.loads(request.body)
        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')

        if not username_or_email or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required.'})

        from django.contrib.auth.models import User
        from django.contrib.auth import authenticate, login as django_login

        # Resolve email to username if they entered email
        username = username_or_email
        if '@' in username_or_email:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                username = user_obj.username
                pass

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                django_login(request, user)
                role = 'admin' if user.is_superuser else 'client'
                # Format username nicely
                username_display = user.first_name if user.first_name else user.username.capitalize()
                return JsonResponse({
                    'success': True,
                    'role': role,
                    'username': username_display
                })
            else:
                return JsonResponse({'success': False, 'error': 'This account is disabled.'})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid username/email or password.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_settings_profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    from .models import UserProfile
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'data': {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': profile.phone,
                'language': profile.language,
                'notify_new_package': profile.notify_new_package,
                'notify_status_update': profile.notify_status_update,
                'notify_payment': profile.notify_payment,
                'company_name': profile.company_name,
                'job_title': profile.job_title,
                'badge_number': profile.badge_number,
                'start_of_day': profile.start_of_day,
                'end_of_day': profile.end_of_day
            }
        })
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Update User
            request.user.first_name = data.get('first_name', request.user.first_name)
            request.user.last_name = data.get('last_name', request.user.last_name)
            request.user.email = data.get('email', request.user.email)
            request.user.save()
            # Update Profile
            profile.phone = data.get('phone', profile.phone)
            profile.language = data.get('language', profile.language)
            profile.notify_new_package = data.get('notify_new_package', profile.notify_new_package)
            profile.notify_status_update = data.get('notify_status_update', profile.notify_status_update)
            profile.notify_payment = data.get('notify_payment', profile.notify_payment)
            profile.company_name = data.get('company_name', profile.company_name)
            profile.job_title = data.get('job_title', profile.job_title)
            profile.badge_number = data.get('badge_number', profile.badge_number)
            profile.start_of_day = data.get('start_of_day', profile.start_of_day)
            profile.end_of_day = data.get('end_of_day', profile.end_of_day)
            profile.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_settings_security(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    if request.method == 'POST':
        try:
            from django.contrib.auth import update_session_auth_hash
            data = json.loads(request.body)
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not request.user.check_password(current_password):
                return JsonResponse({'success': False, 'error': 'Mot de passe actuel incorrect'})
                
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user) # Keep user logged in
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_settings_company(request):
    from .models import CompanySettings
    company = CompanySettings.load()
    
    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'data': {
                'company_name': company.company_name,
                'contact_email': company.contact_email,
                'support_phone': company.support_phone,
                'address': company.address,
                'tax_id': company.tax_id
            }
        })
    elif request.method == 'POST':
        if not request.user.is_authenticated or not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Not authorized'})
        try:
            data = json.loads(request.body)
            company.company_name = data.get('company_name', company.company_name)
            company.contact_email = data.get('contact_email', company.contact_email)
            company.support_phone = data.get('support_phone', company.support_phone)
            company.address = data.get('address', company.address)
            company.tax_id = data.get('tax_id', company.tax_id)
            company.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def api_settings_zones(request):
    from .models import DeliveryZone
    
    if request.method == 'GET':
        zones = list(DeliveryZone.objects.values('id', 'name', 'base_price', 'is_active'))
        return JsonResponse({'success': True, 'data': zones})
        
    elif request.method == 'POST':
        if not request.user.is_authenticated or not request.user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Not authorized'})
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'add':
                DeliveryZone.objects.create(
                    name=data.get('name'),
                    base_price=data.get('base_price', 0)
                )
            elif action == 'toggle':
                zone = DeliveryZone.objects.get(id=data.get('id'))
                zone.is_active = not zone.is_active
                zone.save()
            elif action == 'delete':
                DeliveryZone.objects.filter(id=data.get('id')).delete()
                
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from datetime import timedelta
from logistics.models import Parcel

@csrf_exempt
def api_wallet_data(request):
    if request.method != "GET":
        return JsonResponse({'success': False, 'error': 'GET request required.'})
    
    now = timezone.now()
    filter_type = request.GET.get('filter', 'all')
    
    base_qs = Parcel.objects.filter(status='DELIVERED')
    
    if filter_type == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        filtered_qs = base_qs.filter(updated_at__gte=start_date)
    elif filter_type == 'week':
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        filtered_qs = base_qs.filter(updated_at__gte=start_date)
    elif filter_type == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        filtered_qs = base_qs.filter(updated_at__gte=start_date)
    else:
        filtered_qs = base_qs
        
    DELIVERY_FEE = 20.0
    
    total_paid_qs = filtered_qs.filter(payment_status='PAID')
    total_unpaid_qs = filtered_qs.exclude(payment_status='PAID')
    
    total_earnings = total_paid_qs.count() * DELIVERY_FEE
    pending_earnings = total_unpaid_qs.count() * DELIVERY_FEE
    delivered_count = filtered_qs.count()
    
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_paid_qs = base_qs.filter(updated_at__gte=this_month_start, payment_status='PAID')
    this_month_earnings = this_month_paid_qs.count() * DELIVERY_FEE
    
    chart_qs = base_qs.filter(payment_status='PAID')
    if filter_type == 'today' or filter_type == 'week':
        chart_data = chart_qs.filter(updated_at__gte=now - timedelta(days=7))\
            .annotate(date=TruncDay('updated_at'))\
            .values('date')\
            .annotate(count=Count('id'))\
            .order_by('date')
        labels = [item['date'].strftime('%b %d') for item in chart_data]
        data = [item['count'] * DELIVERY_FEE for item in chart_data]
    else:
        chart_data = chart_qs.annotate(date=TruncMonth('updated_at'))\
            .values('date')\
            .annotate(count=Count('id'))\
            .order_by('date')
        labels = [item['date'].strftime('%b %Y') for item in chart_data]
        data = [item['count'] * DELIVERY_FEE for item in chart_data]
        
    table_data = []
    for p in filtered_qs.order_by('-updated_at')[:50]:
        table_data.append({
            'tracking_number': p.tracking_number,
            'merchant': p.sender_name,
            'amount': float(p.amount),
            'delivery_fee': DELIVERY_FEE,
            'date': p.updated_at.strftime('%Y-%m-%d %H:%M'),
            'status': p.payment_status
        })
        
    return JsonResponse({
        'success': True,
        'summary': {
            'current_balance': total_earnings,
            'total_earnings': total_earnings,
            'delivered_count': delivered_count,
            'pending_earnings': pending_earnings,
            'this_month_earnings': this_month_earnings,
        },
        'chart': {
            'labels': labels,
            'data': data
        },
        'table': table_data
    })
