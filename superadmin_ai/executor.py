"""
AI Operative Executor — pretvara odobrene AI akcije u ORM udarce.

Razdvajanje:
  AI Vijeće (odluka) → PendingAIAction (JSON) → Executor (izvršenje)
  Nema AI koda u poslovnoj logici. Executor čita čisti JSON iz baze.

Moduli:
  b2b_procurement  — automatska kreacija PurchaseOrder
  dynamic_pricing   — dinamički popusti za robu pred istek
  haccp_logistics   — blokada SmartBox + storno robe

Sigurnost:
  - @transaction.atomic — rollback na bilo koji error
  - select_for_update — sprječava duplo izvršavanje
  - Audit log u SystemAuditLog
  - Striktno polja-validirani JSON payloadi
"""
import logging
from decimal import Decimal, InvalidOperation

from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone as tz

logger = logging.getLogger('ai_executor')


class AIExecutionError(Exception):
    """Greška pri parsiranju ili izvršavanju AI payloada."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class AIOperativeExecutor:
    """Neprobojni transakcijski prevoditelj — JSON → ORM."""

    @classmethod
    @transaction.atomic
    def execute_approved_action(cls, pending_action_id, system_user):
        """
        Glavni router. Uzima odobrenu PendingAIAction i delegira handleru.

        Args:
            pending_action_id: PendingAIAction.pk (UUID)
            system_user: User koji predstavlja AI sustav za audit

        Returns:
            dict s rezultatom izvršenja

        Raises:
            AIExecutionError: jasna poruka za log
        """
        from superadmin_ai.models import AIActionLog, PendingAIAction

        # Lock redak — sprječava duplo izvršavanje
        action = PendingAIAction.objects.select_for_update().get(
            pk=pending_action_id, status='approved'
        )

        module = action.module
        payload = action.payload

        handlers = {
            'b2b_procurement': cls._handle_b2b_procurement,
            'dynamic_pricing': cls._handle_dynamic_pricing,
            'haccp_logistics': cls._handle_haccp_logistics,
        }

        handler = handlers.get(module)
        if not handler:
            raise AIExecutionError('UNKNOWN_MODULE', 'Nepoznat executor modul: %s' % module)

        try:
            result = handler(action.company, payload, system_user)

            # Označi kao izvršeno
            action.status = 'executed'
            action.reviewed_at = tz.now()
            action.result = result
            action.save(update_fields=['status', 'reviewed_at', 'result'])

            # Audit log
            AIActionLog.objects.create(
                company=action.company,
                module=module,
                action_type='ai_execute_%s' % action.action_type,
                access_level=4,  # COUNCIL
                outcome='executed',
                user=system_user,
                details={
                    'action_id': str(action.pk),
                    'result': result,
                },
            )

            logger.info('[AI EXECUTOR] Action %s executed: %s', action.pk, module)
            return result

        except AIExecutionError:
            action.status = 'expired'
            action.review_note = 'Execution failed'
            action.save(update_fields=['status', 'review_note'])
            raise

        except (IntegrityError, DatabaseError) as e:
            action.status = 'expired'
            action.review_note = 'Execution error: %s' % str(e)[:200]
            action.save(update_fields=['status', 'review_note'])
            logger.critical('[AI EXECUTOR] Fatal error on action %s: %s', action.pk, e, exc_info=True)
            raise AIExecutionError('EXEC_FAILED', str(e)[:200])

    # ── B2B Procurement ────────────────────────────────────────

    @classmethod
    def _handle_b2b_procurement(cls, company, payload, system_user):
        """
        AI kreira PurchaseOrder na temelju analize zaliha.
        Payload: {"supplier_id": 12, "items": [{"sku": "ABC", "qty": 50}]}
        """
        from inventory.models import InventoryItem
        from partners.models import Partner
        from procurement.models import PurchaseOrder, PurchaseOrderItem

        supplier_id = payload.get('supplier_id')
        items_data = payload.get('items', [])

        if not supplier_id:
            raise AIExecutionError('NO_SUPPLIER', 'Nedostaje supplier_id u payloadu.')
        if not items_data:
            raise AIExecutionError('NO_ITEMS', 'Nedostaje items u payloadu.')

        supplier = Partner.objects.filter(pk=supplier_id, company=company).first()
        if not supplier:
            raise AIExecutionError('SUPPLIER_NOT_FOUND', 'Dobavljač #%s ne postoji.' % supplier_id)

        # Kreiraj PO
        po = PurchaseOrder(
            company=company,
            supplier=supplier,
            created_by=system_user,
            status='draft',
            priority=payload.get('priority', 'normal'),
            notes='AI auto-generated PO',
        )
        po.po_number = po.generate_po_number()
        po.save()

        for item_data in items_data:
            sku = item_data.get('sku', '')
            qty = item_data.get('qty', 0)

            if not sku or not qty:
                continue

            inv_item = InventoryItem.objects.filter(sku=sku, company=company).first()
            if not inv_item:
                raise AIExecutionError(
                    'ITEM_NOT_FOUND', 'Artikl SKU: %s ne postoji u sustavu.' % sku
                )

            try:
                quantity = Decimal(str(qty))
                price = inv_item.purchase_price or Decimal('0')
            except (InvalidOperation, ValueError):
                raise AIExecutionError('INVALID_QTY', 'Neispravna količina za SKU: %s' % sku)

            PurchaseOrderItem.objects.create(
                purchase_order=po,
                inventory_item=inv_item,
                description=inv_item.name,
                sku=inv_item.sku,
                quantity=quantity,
                unit=inv_item.unit or 'kom',
                unit_price=price,
                tax_rate=Decimal('25'),
            )

        po.recalculate()

        # Audit u SystemAuditLog
        cls._audit(system_user, company, 'AI_PO_CREATED',
                   'procurement.PurchaseOrder', str(po.pk),
                   'AI generirao PO %s za %s (%s EUR)' % (po.po_number, supplier.name, po.total))

        return {
            'po_id': po.pk,
            'po_number': po.po_number,
            'supplier': supplier.name,
            'total': str(po.total),
            'items_count': po.items.count(),
        }

    # ── Dynamic Pricing ────────────────────────────────────────

    @classmethod
    def _handle_dynamic_pricing(cls, company, payload, system_user):
        """
        AI reže cijene za robu pred istek roka.
        Payload: {"category_id": 5, "discount_percent": 15, "reason": "Istek roka", "days": 7}
        """
        from marketplace.models import CategoryDiscount

        category_id = payload.get('category_id')
        discount_pct = payload.get('discount_percent')

        if not category_id or not discount_pct:
            raise AIExecutionError('MISSING_FIELDS', 'Nedostaje category_id ili discount_percent.')

        try:
            pct = Decimal(str(discount_pct))
        except (InvalidOperation, ValueError):
            raise AIExecutionError('INVALID_DISCOUNT', 'Neispravan postotak: %s' % discount_pct)

        if pct > 50:
            raise AIExecutionError('DISCOUNT_TOO_HIGH', 'AI ne smije dati popust > 50%%. Traženo: %s%%' % pct)

        days = int(payload.get('days', 7))

        discount = CategoryDiscount.objects.create(
            seller_company=company,
            category_id=category_id,
            discount_percent=pct,
            is_active=True,
        )

        reason = payload.get('reason', 'AI optimizacija zaliha')
        cls._audit(system_user, company, 'AI_DISCOUNT_APPLIED',
                   'marketplace.CategoryDiscount', str(discount.pk),
                   'AI primijenio %s%% popust na kategoriju #%s: %s' % (pct, category_id, reason))

        return {
            'discount_id': discount.pk,
            'category_id': category_id,
            'discount_percent': str(pct),
            'reason': reason,
        }

    # ── HACCP Logistics ────────────────────────────────────────

    @classmethod
    def _handle_haccp_logistics(cls, company, payload, system_user):
        """
        AI blokira SmartBox i zatvara HACCP incident.
        Payload: {"incident_id": 45, "reason": "Kritičan pad temperature"}
        """
        from delivery.models import HACCPIncident

        incident_id = payload.get('incident_id')
        if not incident_id:
            raise AIExecutionError('NO_INCIDENT', 'Nedostaje incident_id.')

        incident = HACCPIncident.objects.select_related('smart_box').filter(
            pk=incident_id
        ).first()

        if not incident:
            raise AIExecutionError('INCIDENT_NOT_FOUND', 'HACCP incident #%s ne postoji.' % incident_id)

        reason = payload.get('reason', 'AI automatska intervencija')

        # Blokiraj SmartBox
        box = incident.smart_box
        if box:
            box.haccp_status = 'blocked'
            box.haccp_blocked_at = tz.now()
            box.save(update_fields=['haccp_status', 'haccp_blocked_at'])

        # Zatvori incident
        incident.severity = 'blocked'
        incident.is_resolved = True
        incident.resolved_by = system_user
        incident.resolution_note = 'AI RESOLUTION: %s' % reason
        incident.resolved_at = tz.now()
        incident.save(update_fields=[
            'severity', 'is_resolved', 'resolved_by',
            'resolution_note', 'resolved_at',
        ])

        # Blokiraj goods receipt
        from delivery.services.cold_chain import ColdChainService
        blocked_receipts = []
        if box:
            blocked_receipts = ColdChainService.block_goods_receipt(box.pk)

        cls._audit(system_user, company, 'AI_HACCP_INTERVENTION',
                   'delivery.HACCPIncident', str(incident.pk),
                   'AI blokirao SmartBox %s i otpisao robu: %s' % (
                       box.box_id if box else '?', reason
                   ))

        return {
            'incident_id': incident.pk,
            'box_id': box.box_id if box else None,
            'box_blocked': True if box else False,
            'receipts_blocked': blocked_receipts,
            'reason': reason,
        }

    # ── Audit Helper ───────────────────────────────────────────

    @staticmethod
    def _audit(user, company, action, model_name, object_id, description):
        """Zapiši u SystemAuditLog."""
        try:
            from core.models import SystemAuditLog
            SystemAuditLog.objects.create(
                user=user,
                company=company,
                action=action,
                model_name=model_name,
                object_id=object_id,
                object_repr=description[:300],
                changes={'ai_executor': True, 'description': description},
            )
        except (IntegrityError, DatabaseError):
            logger.warning('AI executor audit failed', exc_info=True)
