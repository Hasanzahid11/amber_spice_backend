from django.core.exceptions import PermissionDenied
from apps.profiles.models import UserAddress


class AddressService:
    @staticmethod
    def get_user_addresses(user):
        return UserAddress.objects.filter(user=user)

    @staticmethod
    def create_address(user, validated_data: dict) -> UserAddress:
        address = UserAddress.objects.create(user=user, **validated_data)
        return address

    @staticmethod
    def update_address(user, address_id: int, validated_data: dict) -> UserAddress:
        address = UserAddress.objects.filter(user=user, id=address_id).first()
        if not address:
            raise PermissionDenied("Address not found or does not belong to the user.")

        for key, value in validated_data.items():
            setattr(address, key, value)
        address.save()
        return address

    @staticmethod
    def set_default_address(user, address_id: int) -> UserAddress:
        address = UserAddress.objects.filter(user=user, id=address_id).first()
        if not address:
            raise PermissionDenied("Address not found or does not belong to the user.")

        address.is_default = True
        address.save()
        return address

    @staticmethod
    def delete_address(user, address_id: int) -> bool:
        address = UserAddress.objects.filter(user=user, id=address_id).first()
        if not address:
            raise PermissionDenied("Address not found or does not belong to the user.")

        was_default = address.is_default
        address.delete()

        # If deleted address was default, promote next available address to default
        if was_default:
            next_address = UserAddress.objects.filter(user=user).first()
            if next_address:
                next_address.is_default = True
                next_address.save()

        return True

