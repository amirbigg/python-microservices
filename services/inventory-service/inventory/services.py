from django.db import IntegrityError, transaction

from .models import InventoryItem, StockReservation


class InsufficientStock(Exception):
    pass


class ReservationConflict(Exception):
    pass


@transaction.atomic
def _reserve_stock(reservation_id, product_id, quantity):
    item = InventoryItem.objects.select_for_update().get(product_id=product_id)
    existing = StockReservation.objects.select_for_update().filter(reservation_id=reservation_id).first()

    if existing:
        same_request = (existing.inventory_item.id == item.pk and existing.quantity == quantity)

        if not same_request:
            raise ReservationConflict("This reservation ID belongs to a different request.")

        if existing.status == StockReservation.Status.RESERVED:
            raise ReservationConflict("A released reservation ID cannot be reused.")

        return existing, False

    if item.quantity < quantity:
        raise InsufficientStock("Not enough available stock.")

    item.quantity -= quantity
    item.save(update_fields=["quantity", "updated"])

    reservation = StockReservation.objects.create(reservation_id=reservation_id, inventory_item=item,
                                                  quantity=quantity, status=StockReservation.Status.RESERVED)

    return reservation, True


def reserve_stock(reservation_id, product_id, quantity):
    try:
        return _reserve_stock(reservation_id, product_id, quantity)
    except IntegrityError:
        existing = StockReservation.objects.select_for_update().filter(reservation_id=reservation_id).first()

        if existing is None:
            raise

        same_request = (existing.inventory_item.product_id == product_id and existing.quantity == quantity)

        if (same_request and existing.status
                in (StockReservation.Status.RESERVED, StockReservation.Status.CONFIRMED)):
            return existing, False

        raise ReservationConflict("This reservation ID has already been used.")


@transaction.atomic
def release_stock(reservation_id):
    reservation_ref = StockReservation.objects.only("inventory_item_id").get(reservation_id=reservation_id)

    item = InventoryItem.objects.select_for_update().get(pk=reservation_ref.inventory_item.id)
    reservation = StockReservation.objects.select_for_update().get(reservation_id=reservation_id)

    if reservation.status == StockReservation.Status.RELEASED:
        return reservation, False

    if reservation.status == StockReservation.Status.CONFIRMED:
        raise ReservationConflict("A confirmed reservation cannot be released.")

    item.quantity += reservation.quantity
    item.save(update_fields=["quantity", "updated"])

    reservation.status = StockReservation.Status.RELEASED
    reservation.save(update_fields=["status", "updated"])

    return reservation, True


@transaction.atomic
def confirm_stock(reservation_id):
    reservation_ref = StockReservation.objects.only("inventory_item_id").get(reservation_id=reservation_id)

    InventoryItem.objects.select_for_update().get(pk=reservation_ref.inventory_item.id)
    reservation = StockReservation.objects.select_for_update().get(reservation_id=reservation_id)

    if reservation.status == StockReservation.Status.RELEASED:
        raise ReservationConflict("A released reservation cannot be confirmed.")

    if reservation.status == StockReservation.Status.CONFIRMED:
        return reservation, False

    reservation.status = StockReservation.Status.CONFIRMED
    reservation.save(update_fields=["status", "updated"])

    return reservation, True
