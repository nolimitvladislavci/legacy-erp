"""
B2B Bridge Service — DMZ između procurement i marketplace.

Rješava "nagaznu minu": Partner (lokalni adresar) vs Company (globalni tenant).
Restoran nikad ne pristupa bazi dobavljača direktno.

Tok:
  PurchaseOrder (kupac) → B2BBridge → MarketplaceOrder + SellerSubOrder (dobavljač)

Sigurnost:
  - Mapiranje Partner → Company isključivo preko OIB-a (porezni broj)
  - @transaction.atomic — sve ili ništa
  - Soft-lock zaliha kod dobavljača
  - Audit log preko SystemAuditLog
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.db import IntegrityError, DatabaseError

logger = logging.getLogger('b2b_bridge')


class B2BBridgeError(Exception):
    """Greška koja prekida transakciju i vraća jasnu poruku kupcu."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class B2BBridgeService:
    """DMZ servis: pretvara PurchaseOrder u MarketplaceOrder bez tenant curenja."""

    @staticmethod
    def _resolve_seller(supplier):
        """
        Mapira Partner (lokalni adresar kupca) → Company (globalni tenant).
        Ključ: OIB (porezni identifikacijski broj) — jedinstven i nepromjenjiv.
        """
        from companies.models import Company

        oib = getattr(supplier, 'oib', None)
        if not oib or not oib.strip():
            raise B2BBridgeError(
                'NO_OIB',
                'Dobavljač "%s" nema unesen OIB. B2B prijenos nije moguć.' % supplier.name
            )

        seller = Company.objects.filter(oib=oib.strip()).first()
        if not seller:
            raise B2BBridgeError(
                'NOT_ON_PLATFORM',
                'Dobavljač "%s" (OIB: %s) nije registriran na LIMIT Connect.' % (supplier.name, oib)
            )

        return seller

    @staticmethod
    def _find_product(seller_company, sku):
        """
        Traži artikl u JAVNOM katalogu dobavljača po SKU-u.
        Kupac ne vidi internu bazu — samo marketplace listing.
        """
        from marketplace.models import MarketplaceProduct

        product = MarketplaceProduct.objects.filter(
            seller_company=seller_company,
            inventory_item__sku=sku,
            is_active=True,
        ).select_related('inventory_item').first()

        return product

    @staticmethod
    def resolve_price(product, quantity, seller_company, buyer_company):
        """
        Provjera cijene: PartnerDiscount > SupplierPriceList > product.price.
        Poziva se opcionalno — transmit_purchase_order koristi product.price po defaultu.
        """
        from django.db.models import Q
        from marketplace.models import PartnerDiscount
        from procurement.models import SupplierPriceList

        # 1. Partner-specifični popust
        discount = PartnerDiscount.objects.filter(
            seller_company=seller_company,
            buyer_company=buyer_company,
        ).first()
        if discount and discount.discount_percent:
            return product.price * (1 - discount.discount_percent / 100)

        # 2. Cjenik dobavljača (najnoviji s min_quantity <= tražene količine)
        price_entry = SupplierPriceList.objects.filter(
            inventory_item=product.inventory_item,
            valid_from__lte=timezone.now().date(),
            min_quantity__lte=quantity,
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date())
        ).order_by('-min_quantity').first()

        if price_entry:
            return price_entry.agreed_price

        # 3. Fallback: marketplace cijena
        return product.price

    @classmethod
    @transaction.atomic
    def transmit_purchase_order(cls, po_id, buyer_user):
        """
        Glavni Gateway. Pretvara PurchaseOrder → MarketplaceOrder + SellerSubOrder.

        Args:
            po_id: PurchaseOrder.pk
            buyer_user: User koji šalje narudžbu

        Returns:
            dict s sub_order_id, market_order_id, items_count, total

        Raises:
            B2BBridgeError: s kodom i porukom za UI
        """
        from procurement.models import PurchaseOrder
        from marketplace.models import (
            MarketplaceOrder, MarketplaceOrderItem, SellerSubOrder,
        )

        # 1. Učitaj PO s relacijama
        po = (
            PurchaseOrder.objects
            .select_related('company', 'supplier')
            .prefetch_related('items__inventory_item')
            .get(pk=po_id)
        )

        if po.status != 'draft':
            raise B2BBridgeError('NOT_DRAFT', 'Samo draft narudžbe mogu biti poslane na Marketplace.')

        if not po.supplier:
            raise B2BBridgeError('NO_SUPPLIER', 'Narudžbenica nema odabranog dobavljača.')

        if not po.items.exists():
            raise B2BBridgeError('EMPTY_PO', 'Narudžbenica nema stavki.')

        # 2. Mapiraj Partner → Company (OIB most)
        seller_company = cls._resolve_seller(po.supplier)

        # 3. Kreiraj MarketplaceOrder (kupčev pogled)
        market_order = MarketplaceOrder.objects.create(
            buyer_company=po.company,
            buyer_user=buyer_user,
            status='pending',
        )

        # 4. Kreiraj SellerSubOrder (dobavljačev pogled)
        sub_order = SellerSubOrder.objects.create(
            marketplace_order=market_order,
            seller_company=seller_company,
            status='pending',
            pickup_address=getattr(seller_company, 'address', '') or '',
        )

        # 5. Prenesi stavke s validacijom zaliha
        total = Decimal('0')
        items_count = 0

        for po_item in po.items.all():
            product = cls._find_product(seller_company, po_item.sku)

            if not product:
                raise B2BBridgeError(
                    'PRODUCT_NOT_FOUND',
                    'Artikl SKU: %s nije dostupan u katalogu dobavljača "%s".' % (
                        po_item.sku, seller_company.name
                    )
                )

            if product.stock < po_item.quantity:
                raise B2BBridgeError(
                    'INSUFFICIENT_STOCK',
                    'Nedovoljne zalihe za "%s". Traženo: %s, dostupno: %s.' % (
                        product.name, po_item.quantity, product.stock
                    )
                )

            # Cijena iz marketplace kataloga (kupac ne diktira cijenu)
            unit_price = product.price
            line_total = unit_price * po_item.quantity

            MarketplaceOrderItem.objects.create(
                order=market_order,
                product=product,
                seller_company=seller_company,
                quantity=po_item.quantity,
                unit_price=unit_price,
                total=line_total,
            )

            # Soft-lock zaliha
            product.stock -= po_item.quantity
            product.save(update_fields=['stock'])

            total += line_total
            items_count += 1

        # 6. Update sub_order totals
        commission = total * sub_order.commission_percent / 100
        sub_order.subtotal = total
        sub_order.commission_amount = commission
        sub_order.seller_payout = total - commission
        sub_order.save(update_fields=[
            'subtotal', 'commission_amount', 'seller_payout',
        ])

        # 7. Zaključaj PO
        po.status = 'sent'
        po.save(update_fields=['status', 'updated_at'])

        # 8. Audit log
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=buyer_user,
                company=po.company,
                action='b2b_transmit',
                model_name='procurement.PurchaseOrder',
                object_id=str(po.pk),
                object_repr='PO %s → %s (%s stavki, %s EUR)' % (
                    po.po_number, seller_company.name, items_count, total
                ),
                changes={
                    'po_id': po.pk,
                    'market_order_id': market_order.pk,
                    'sub_order_id': sub_order.pk,
                    'seller_oib': seller_company.oib,
                    'total': str(total),
                },
            )
        except (IntegrityError, DatabaseError):
            logger.warning('B2B audit log failed for PO %s', po.pk, exc_info=True)

        logger.info(
            '[B2B BRIDGE] PO %s → SubOrder %s (seller: %s, total: %s EUR)',
            po.po_number, sub_order.pk, seller_company.name, total
        )

        return {
            'sub_order_id': sub_order.pk,
            'market_order_id': market_order.pk,
            'seller': seller_company.name,
            'items_count': items_count,
            'total': str(total),
        }
