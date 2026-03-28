"""
udruge/consumers.py — WebSocket consumer for live pigeon auctions.

Anti-sniping: Bid in last 60s resets timer to +30s.
Flow:
  1. Client connects to ws://host/ws/auction/<product_id>/
  2. Server streams: current_bid, timer, bid_count
  3. Client sends: {"type": "bid", "amount": 150.00}
  4. Server validates, broadcasts to all watchers
  5. Timer hits 0 → auction_end: auto-invoice + golub status "Prodano"
"""
import json
import logging
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger('auction')

ANTI_SNIPE_WINDOW = 60     # seconds — bids in this window trigger extension
ANTI_SNIPE_EXTEND = 30     # seconds — how much to extend


class AuctionConsumer(AsyncJsonWebsocketConsumer):
    """Live auction WebSocket for pigeon (and other collectible) auctions."""

    async def connect(self):
        self.product_id = self.scope['url_route']['kwargs']['product_id']
        self.room_group = f'auction_{self.product_id}'
        self.user = self.scope.get('user')

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Send current state
        state = await self.get_auction_state()
        await self.send_json(state)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type', '')

        if msg_type == 'bid':
            await self.handle_bid(content)
        elif msg_type == 'ping':
            state = await self.get_auction_state()
            await self.send_json(state)

    async def handle_bid(self, content):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.send_json({'type': 'error', 'message': 'Morate biti prijavljeni.'})
            return

        try:
            amount = Decimal(str(content.get('amount', '0')))
        except (InvalidOperation, ValueError):
            await self.send_json({'type': 'error', 'message': 'Neispravan iznos.'})
            return

        if amount <= 0:
            await self.send_json({'type': 'error', 'message': 'Iznos mora biti pozitivan.'})
            return

        result = await self.process_bid(user, amount)

        if result.get('error'):
            await self.send_json({'type': 'error', 'message': result['error']})
        else:
            # Broadcast to all watchers
            await self.channel_layer.group_send(
                self.room_group,
                {
                    'type': 'auction_update',
                    'data': result,
                }
            )

    async def auction_update(self, event):
        """Broadcast handler — sends update to individual client."""
        await self.send_json(event['data'])

    async def auction_ended(self, event):
        """Broadcast handler — auction has ended."""
        await self.send_json(event['data'])

    @database_sync_to_async
    def get_auction_state(self):
        from marketplace.models import MarketplaceProduct

        try:
            product = MarketplaceProduct.objects.get(pk=self.product_id)
        except MarketplaceProduct.DoesNotExist:
            return {'type': 'error', 'message': 'Aukcija ne postoji.'}

        now = timezone.now()
        expires_at = product.expires_at
        remaining = (expires_at - now).total_seconds() if expires_at else 0
        remaining = max(0, remaining)

        # Top 5 bids
        top_bids = list(
            product.bids.select_related('bidder_company')
            .order_by('-amount')[:5]
            .values('bidder_company__name', 'amount', 'created_at')
        )
        for b in top_bids:
            b['amount'] = str(b['amount'])
            b['created_at'] = b['created_at'].isoformat()

        return {
            'type': 'state',
            'product_id': product.pk,
            'name': product.name,
            'current_bid': str(product.current_bid or product.starting_bid or product.unit_price),
            'starting_bid': str(product.starting_bid or product.unit_price),
            'bid_count': product.bid_count,
            'remaining_seconds': int(remaining),
            'expires_at': expires_at.isoformat() if expires_at else None,
            'auction_status': product.auction_status or ('active' if remaining > 0 else 'sold'),
            'top_bids': top_bids,
            'is_ending_soon': remaining < ANTI_SNIPE_WINDOW,
        }

    @database_sync_to_async
    def process_bid(self, user, amount):
        from marketplace.models import MarketplaceProduct, AuctionBid
        from core.company_utils import get_user_company_from_user
        from django.db import transaction

        try:
            with transaction.atomic():
                product = MarketplaceProduct.objects.select_for_update().get(pk=self.product_id)

                # Validation
                if not product.is_auction:
                    return {'error': 'Ovaj proizvod nije na aukciji.'}

                now = timezone.now()
                if product.expires_at and now >= product.expires_at:
                    return {'error': 'Aukcija je zavrsena.'}

                current = product.current_bid or product.starting_bid or product.unit_price
                min_bid = current + Decimal('1')  # min increment 1 EUR

                if amount < min_bid:
                    return {'error': f'Minimalna ponuda je {min_bid} EUR (trenutna: {current} EUR).'}

                company = get_user_company_from_user(user)
                if not company:
                    return {'error': 'Nemate aktivnu tvrtku.'}

                if company.pk == product.seller_company_id:
                    return {'error': 'Ne mozete licitirati na vlastiti proizvod.'}

                # Create bid
                bid = AuctionBid.objects.create(
                    product=product,
                    bidder_company=company,
                    bidder_user=user,
                    amount=amount,
                )

                # Update product
                product.current_bid = amount
                product.bid_count = product.bids.count()
                update_fields = ['current_bid', 'bid_count']

                # ANTI-SNIPING: bid in last 60s → extend +30s
                remaining = (product.expires_at - now).total_seconds() if product.expires_at else 999
                extended = False
                if remaining < ANTI_SNIPE_WINDOW:
                    product.expires_at = product.expires_at + timedelta(seconds=ANTI_SNIPE_EXTEND)
                    product.auction_status = 'ending_soon'
                    update_fields.extend(['expires_at', 'auction_status'])
                    extended = True

                product.save(update_fields=update_fields)

                new_remaining = (product.expires_at - now).total_seconds() if product.expires_at else 0

                return {
                    'type': 'new_bid',
                    'product_id': product.pk,
                    'current_bid': str(amount),
                    'bid_count': product.bid_count,
                    'bidder': company.name,
                    'remaining_seconds': int(max(0, new_remaining)),
                    'expires_at': product.expires_at.isoformat() if product.expires_at else None,
                    'extended': extended,
                    'anti_snipe': extended,
                    'is_ending_soon': new_remaining < ANTI_SNIPE_WINDOW,
                }

        except MarketplaceProduct.DoesNotExist:
            return {'error': 'Proizvod ne postoji.'}
        except Exception as e:
            logger.error('Bid error product %s: %s', self.product_id, e, exc_info=True)
            return {'error': 'Greska pri obradi ponude.'}
