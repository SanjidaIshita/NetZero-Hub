from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import Booking, BookingEvent, CollectionSlot, Notification, Provider, WasteType

User = get_user_model()

postcode_validator = RegexValidator(r"^\d{4}$", "Enter a valid 4-digit Australian postcode.")
phone_validator = RegexValidator(r"^\+?[\d\s()-]{8,20}$", "Enter a valid phone number.")


# --- auth -----------------------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name", "is_staff"]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password(attrs["password"], User(username=attrs["username"], email=attrs["email"]))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})


# --- reference data ---------------------------------------------------------------------------


class WasteTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteType
        fields = ["code", "name", "description", "accepted_items", "is_special", "base_fee"]


class ProviderContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ["name", "phone", "email", "website"]


class SlotSerializer(serializers.ModelSerializer):
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = CollectionSlot
        fields = ["id", "date", "start_time", "end_time", "remaining"]


# --- inputs -----------------------------------------------------------------------------------


class AvailabilityQuerySerializer(serializers.Serializer):
    postcode = serializers.CharField(validators=[postcode_validator])
    waste_type = serializers.SlugRelatedField(slug_field="code", queryset=WasteType.objects.filter(active=True))
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class QuoteSerializer(serializers.Serializer):
    waste_type = serializers.SlugRelatedField(slug_field="code", queryset=WasteType.objects.filter(active=True))
    quantity = serializers.ChoiceField(choices=Booking.Quantity.choices, default=Booking.Quantity.SMALL)


class BookingCreateSerializer(serializers.Serializer):
    """WMS-002 service inputs. Authentication information is the request's auth token."""

    customer_name = serializers.CharField(max_length=150)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=30, validators=[phone_validator])
    address_line = serializers.CharField(max_length=255)
    suburb = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postcode = serializers.CharField(validators=[postcode_validator])
    waste_type = serializers.SlugRelatedField(slug_field="code", queryset=WasteType.objects.all())
    quantity = serializers.ChoiceField(choices=Booking.Quantity.choices, default=Booking.Quantity.SMALL)
    special_instructions = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    slot_id = serializers.IntegerField(help_text="Id of a slot returned by /availability/ (preferred date).")
    accept_fee = serializers.BooleanField(default=False, help_text="Must be true when the quote is non-zero.")
    payment_token = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="Token from the payment provider (fee only)."
    )


class RescheduleSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()


class MissedCollectionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


# --- outputs ----------------------------------------------------------------------------------


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "recipient", "subject", "message", "delivered", "created_at"]


class BookingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingEvent
        fields = ["status", "note", "created_at"]


class BookingOutputSerializer(serializers.ModelSerializer):
    """The WMS-002 Service Output contract, shared by the resident, provider and integration APIs.

    booking reference, confirmed collection date/time, waste type information, provider
    contact details, booking status and the notification sent to the resident.
    """

    service_id = serializers.SerializerMethodField()
    booking_reference = serializers.CharField(source="reference")
    booking_status = serializers.CharField(source="status")
    confirmed_collection = serializers.SerializerMethodField()
    waste_type = WasteTypeSerializer()
    estimated_quantity = serializers.CharField(source="quantity")
    provider_contact = ProviderContactSerializer(source="provider", allow_null=True)
    collection_address = serializers.SerializerMethodField()
    special_instructions = serializers.CharField()
    fee = serializers.SerializerMethodField()
    notification = serializers.SerializerMethodField()
    rejection_reason = serializers.CharField()

    class Meta:
        model = Booking
        fields = [
            "service_id",
            "booking_reference",
            "booking_status",
            "confirmed_collection",
            "waste_type",
            "estimated_quantity",
            "provider_contact",
            "collection_address",
            "special_instructions",
            "fee",
            "notification",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]

    def get_service_id(self, obj) -> str:
        return settings.RECYCLING["SERVICE_ID"]

    def get_confirmed_collection(self, obj) -> dict:
        if obj.slot is None or obj.status in (
            Booking.Status.REJECTED,
            Booking.Status.PENDING,
            Booking.Status.CANCELLED,
        ):
            return None
        return {
            "date": obj.slot.date.isoformat(),
            "start_time": obj.slot.start_time.strftime("%H:%M"),
            "end_time": obj.slot.end_time.strftime("%H:%M"),
        }

    def get_collection_address(self, obj) -> dict:
        return {"address_line": obj.address_line, "suburb": obj.suburb, "postcode": obj.postcode}

    def get_fee(self, obj) -> dict:
        payment = getattr(obj, "payment", None)
        return {
            "amount": str(obj.fee),
            "currency": settings.RECYCLING["CURRENCY"],
            "chargeable": obj.fee > 0,
            "receipt_number": payment.receipt_number if payment else None,
            "payment_status": payment.status if payment else None,
        }

    def get_notification(self, obj) -> dict:
        latest = obj.notifications.order_by("-created_at", "-id").first()
        if latest is None:
            return None
        return {
            "kind": latest.kind,
            "recipient": latest.recipient,
            "subject": latest.subject,
            "delivered": latest.delivered,
            "sent_at": latest.created_at,
        }


class BookingSerializer(BookingOutputSerializer):
    """Resident view of a booking: the service output plus contact details and history."""

    customer_name = serializers.CharField()
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField()
    slot = SlotSerializer(allow_null=True)
    can_change = serializers.BooleanField()
    change_deadline = serializers.DateTimeField(allow_null=True)
    missed_count = serializers.IntegerField()
    events = BookingEventSerializer(many=True)

    class Meta(BookingOutputSerializer.Meta):
        fields = BookingOutputSerializer.Meta.fields + [
            "customer_name",
            "customer_email",
            "customer_phone",
            "slot",
            "can_change",
            "change_deadline",
            "missed_count",
            "events",
        ]


class ProviderCollectionSerializer(BookingOutputSerializer):
    """Run-sheet row for the provider/staff: the service output plus who booked it."""

    resident = serializers.SerializerMethodField()

    class Meta(BookingOutputSerializer.Meta):
        fields = BookingOutputSerializer.Meta.fields + ["resident"]

    def get_resident(self, obj) -> dict:
        return {
            "user_id": obj.user_id,
            "username": obj.user.username,
            "name": obj.customer_name,
            "phone": obj.customer_phone,
            "email": obj.customer_email,
        }
