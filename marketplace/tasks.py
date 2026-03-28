"""
marketplace/tasks.py — Celery taskovi za Ghost Inventory i notifikacije.
"""
import logging
from celery import shared_task

logger = logging.getLogger('marketplace')


@shared_task(bind=True, soft_time_limit=120)
def ghost_inventory_cleanup(self):
    """
    Svakih 6h — deaktivira expired marketplace listinge.
    Sprečava "ghost inventory" — proizvode koji više nisu dostupni.
    """
    from marketplace.services.marketplace_bridge import deactivate_expired_listings
    return deactivate_expired_listings()


@shared_task(bind=True, soft_time_limit=120)
def send_expiry_reminders(self):
    """
    Svakih 6h — šalje "Još dostupno? Da/Ne" push notif za listinge koji uskoro ističu.
    Prodavač može 1 tapom refreshati listing.
    """
    from marketplace.services.marketplace_bridge import get_expiring_soon, EXPIRY_RULES
    from datetime import timedelta

    expiring = get_expiring_soon(hours=6)
    notified = 0

    for product in expiring:
        try:
            # Pokušaj WhatsApp notif
            from core.whatsapp import send_text
            from accounts.models import UserProfile

            # Nađi admina seller company
            admin_profile = UserProfile.objects.filter(
                company=product.seller_company
            ).select_related('user').first()

            if admin_profile and admin_profile.user:
                phone = getattr(admin_profile, 'phone', '') or ''
                if phone:
                    msg = (
                        f'🔔 Vaš listing "{product.name}" na tržnici ističe uskoro. '
                        f'Još dostupno? Posjetite tržnicu za produljenje.'
                    )
                    send_text(
                        phone=phone,
                        message=msg,
                        company_id=str(product.seller_company.pk),
                    )
                    notified += 1
        except Exception as e:
            logger.warning('Expiry reminder %s: %s', product.pk, e)

    logger.info('Expiry reminders: %d notified of %d expiring', notified, expiring.count())
    return {'expiring': expiring.count(), 'notified': notified}



@shared_task(bind=True, soft_time_limit=120)
def expiry_gastro_bridge_check(self):
    """
    Svakih 2h — provjerava marketplace listinge koji isticu za 4h ili manje.
    Za kvarljive proizvode (jaja, voce), nudi prebacivanje na gastro meni s popustom.
    Salje WhatsApp s deep-linkom za 1-click akciju.
    """
    from marketplace.models import MarketplaceProduct
    from marketplace.services.marketplace_bridge import PERISHABLE_MODELS
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    threshold = now + timedelta(hours=4)

    # Kvarljivi proizvodi koji isticu za <4h i jos su aktivni
    expiring_perishable = MarketplaceProduct.objects.filter(
        auto_listed=True,
        is_available=True,
        source_model__in=list(PERISHABLE_MODELS),
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=threshold,
    ).select_related("seller_company")

    bridged = 0
    for product in expiring_perishable:
        try:
            from core.whatsapp import send_text
            from accounts.models import UserProfile

            admin_profile = UserProfile.objects.filter(
                company=product.seller_company
            ).select_related("user").first()

            if admin_profile and admin_profile.user:
                phone = getattr(admin_profile, "phone", "") or ""
                if phone:
                    bridge_url = f"https://limit-connect.com/marketplace/gastro-bridge/{product.pk}/"
                    msg = (
                        f"LAST CALL: {product.name} istice za ~4h na trznici. "
                        f"→ {bridge_url}"
                    )
                    send_text(phone=phone, message=msg, company_id=str(product.seller_company.pk))
                    bridged += 1
        except Exception as e:
            logger.warning("Gastro bridge notify %s: %s", product.pk, e)

    logger.info("Gastro bridge check: %d perishable expiring, %d notified", expiring_perishable.count(), bridged)
    return {"expiring_perishable": expiring_perishable.count(), "notified": bridged}


@shared_task(bind=True, soft_time_limit=120)
def finalize_ended_auctions(self):
    """
    Svakih 5 min — provjerava aukcije kojima je timer istekao.
    Za svaku:
      1. Oznaci winning bid
      2. Generiraj predracun (POS draft)
      3. Posalji WhatsApp kupcu + prodavacu
      4. Update golub status = "Prodano - Ceka transport"
    """
    from marketplace.models import MarketplaceProduct, AuctionBid
    from django.utils import timezone

    now = timezone.now()
    ended = MarketplaceProduct.objects.filter(
        is_auction=True,
        auction_status__in=('active', 'ending_soon'),
        expires_at__isnull=False,
        expires_at__lt=now,
    )

    results = {'finalized': 0, 'no_bids': 0, 'errors': 0}

    for product in ended:
        try:
            winning_bid = product.bids.order_by('-amount').first()

            if winning_bid:
                # Mark winning bid
                winning_bid.is_winning = True
                winning_bid.save(update_fields=['is_winning'])

                # Update product
                product.auction_status = 'sold'
                product.is_available = False
                product.save(update_fields=['auction_status', 'is_available'])

                # Generate draft invoice
                try:
                    from invoicing.models import Invoice, InvoiceLine
                    invoice = Invoice.objects.create(
                        company=product.seller_company,
                        partner_name=winning_bid.bidder_company.name,
                        partner_oib=getattr(winning_bid.bidder_company, 'oib', ''),
                        invoice_type='predracun',
                        status='draft',
                        notes='Aukcija goluba %s — Winning bid: %s EUR' % (
                            product.name, winning_bid.amount
                        ),
                    )
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        description=product.name,
                        quantity=1,
                        unit_price=winning_bid.amount,
                        vat_rate=25,
                    )
                    invoice.recalculate()
                    logger.info('Auction invoice #%s for product %s', invoice.pk, product.pk)
                except Exception as e:
                    logger.warning('Auction invoice failed for %s: %s', product.pk, e)

                # Update golub status if source is Golub
                if product.source_model == 'Golub' and product.source_id:
                    try:
                        from udruge.models import Golub
                        golub = Golub.objects.get(pk=product.source_id)
                        golub.aktivan = False
                        golub.napomena = (golub.napomena or '') + (
                            '\nPRODANO na aukciji %s — Kupac: %s, Cijena: %s EUR' % (
                                now.strftime('%d.%m.%Y %H:%M'),
                                winning_bid.bidder_company.name,
                                winning_bid.amount,
                            )
                        )
                        golub.save(update_fields=['aktivan', 'napomena'])
                    except Exception:
                        pass

                # WhatsApp notifications
                try:
                    from core.whatsapp import send_text
                    from accounts.models import UserProfile

                    # Notify seller
                    seller_profile = UserProfile.objects.filter(
                        company=product.seller_company
                    ).first()
                    if seller_profile and getattr(seller_profile, 'phone', ''):
                        send_text(
                            phone=seller_profile.phone,
                            message=(
                                'PRODANO! Golub "%s" prodan za %s EUR.\n'
                                'Kupac: %s\n'
                                'Predracun kreiran. Dogovorite transport.'
                            ) % (product.name, winning_bid.amount, winning_bid.bidder_company.name),
                            company_id=str(product.seller_company.pk),
                        )

                    # Notify buyer
                    buyer_profile = UserProfile.objects.filter(
                        company=winning_bid.bidder_company
                    ).first()
                    if buyer_profile and getattr(buyer_profile, 'phone', ''):
                        send_text(
                            phone=buyer_profile.phone,
                            message=(
                                'Cestitamo! Pobijedili ste na aukciji za "%s" — %s EUR.\n'
                                'Predracun ce stici na email. Kontaktirajte prodavaca za transport.'
                            ) % (product.name, winning_bid.amount),
                            company_id=str(winning_bid.bidder_company.pk),
                        )
                except Exception as e:
                    logger.warning('Auction notification failed: %s', e)

                results['finalized'] += 1

            else:
                # No bids — mark as no_bids
                product.auction_status = 'no_bids'
                product.is_available = False
                product.save(update_fields=['auction_status', 'is_available'])
                results['no_bids'] += 1

        except Exception as e:
            logger.error('Auction finalize error for product %s: %s', product.pk, e, exc_info=True)
            results['errors'] += 1

    if any(results.values()):
        logger.info('Auction finalization: %s', results)
    return results
