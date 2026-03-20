from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from .models import TrackingStatus, TrackedItem, TrackingEvent


class TrackingStatusTest(TestCase):
    def test_create_status(self):
        s = TrackingStatus.objects.create(
            tracking_type='food_order', name='Primljeno',
            slug='primljeno', order=1,
        )
        self.assertEqual(str(s), 'Narudzba hrane / Primljeno')

    def test_unique_together(self):
        TrackingStatus.objects.create(
            tracking_type='food_order', name='A', slug='a', order=1,
        )
        with self.assertRaises(Exception):
            TrackingStatus.objects.create(
                tracking_type='food_order', name='B', slug='a', order=2,
            )


class TrackedItemTest(TestCase):
    def setUp(self):
        self.status = TrackingStatus.objects.create(
            tracking_type='food_order', name='Nova', slug='nova', order=1,
        )
        self.ct = ContentType.objects.get_for_model(User)
        self.user = User.objects.create_user('tracker_test', password='test123')

    def test_auto_token(self):
        item = TrackedItem.objects.create(
            content_type=self.ct, object_id=self.user.pk,
            tracking_type='food_order',
        )
        self.assertEqual(len(item.public_token), 32)

    def test_update_status(self):
        item = TrackedItem.objects.create(
            content_type=self.ct, object_id=self.user.pk,
            tracking_type='food_order',
        )
        event = item.update_status(self.status, user=self.user, note='test')
        self.assertEqual(item.current_status, self.status)
        self.assertEqual(event.status, self.status)
        self.assertEqual(event.note, 'test')
        self.assertEqual(TrackingEvent.objects.filter(tracked_item=item).count(), 1)
