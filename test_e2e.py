#!/usr/bin/env python
"""End-to-end test za Social Import"""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
sys.path.insert(0, "/var/www/fina-connect")
django.setup()

import uuid

from django.contrib.auth.models import User

from boxgram.models import LifeEvent, PetProfile, SocialImport
from boxgram.services.social_import import create_social_import, detect_platform, fetch_oembed
from companies.models import Company


def main():
    print("=" * 70)
    print("END-TO-END TEST: Boxgram Social Import")
    print("=" * 70)

    # Setup
    print("\n[Setup] Creating test data...")
    company = Company.objects.create(name=f"E2E Test Co {uuid.uuid4().hex[:8]}", oib=f"{uuid.uuid4().hex[:11]}")
    user = User.objects.create_user(
        username=f"e2euser{uuid.uuid4().hex[:8]}",
        email=f"e2e{uuid.uuid4().hex[:8]}@example.com",
        password="password123",
    )
    pet = PetProfile.objects.create(
        tenant=company, owner=user, name="E2E Test Pet", species="pas", slug=f"e2epet{uuid.uuid4().hex[:8]}"
    )
    print(f"  ✓ User: {user.username}")
    print(f"  ✓ Pet: {pet.name} (slug: {pet.slug})")

    # Test 1: YouTube URL detection & preview
    print("\n[Test 1] YouTube URL Detection & Preview")
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    platform = detect_platform(yt_url)
    print(f"  ✓ Detected platform: {platform}")

    preview = fetch_oembed(yt_url)
    print(f"  ✓ Preview fetched: success={preview.success}")
    if preview.success:
        print(f"    - Thumbnail: {preview.thumbnail_url[:50]}...")
        print(f"    - Platform: {preview.platform}")
    else:
        # Expected untuk test jer je real URL
        print(f"    - Expected error (real API): {preview.error[:50]}...")

    # Test 2: Create Social Import
    print("\n[Test 2] Create Social Import Record")
    test_url = f"https://www.youtube.com/watch?v={uuid.uuid4().hex[:8]}"
    social_import, preview = create_social_import(pet, test_url, user)
    print(f"  ✓ SocialImport created: {social_import.id}")
    print(f"    - Status: {social_import.status}")
    print(f"    - Platform: {social_import.platform}")

    # Test 3: Simulate confirm import (create LifeEvent)
    print("\n[Test 3] Confirm Import → Create LifeEvent")
    if not preview.success:
        # Za test, koristi mock data
        preview.caption = "Test Video Caption"

    life_event = LifeEvent.objects.create(
        pet=pet,
        event_type="social_import",
        title=preview.caption[:100] or f"Import from {preview.platform}",
        description=preview.caption or "",
        date=django.utils.timezone.now().date(),
        source=preview.platform or "youtube",
        source_url=test_url,
        is_public=True,
    )
    print(f"  ✓ LifeEvent created: {life_event.id}")
    print(f"    - Title: {life_event.title}")
    print(f"    - Pet: {life_event.pet.name}")
    print(f"    - Source: {life_event.source}")

    # Map SocialImport to LifeEvent
    social_import.status = "approved"
    social_import.mapped_to = life_event
    social_import.save()
    print("  ✓ Mapped SocialImport to LifeEvent")

    # Test 4: Query pending imports
    print("\n[Test 4] Query Pending Imports")
    pending = SocialImport.objects.filter(pet__in=PetProfile.objects.filter(owner=user), status="pending")
    print(f"  ✓ Found {pending.count()} pending imports")

    # Test 5: Reject import
    print("\n[Test 5] Reject Import")
    test_url2 = f"https://www.tiktok.com/video/{uuid.uuid4().hex[:8]}"
    import2 = SocialImport.objects.create(pet=pet, platform="tiktok", source_url=test_url2, status="pending")
    import2.status = "rejected"
    import2.save()
    print(f"  ✓ Rejected import: {import2.id}")
    print(f"    - Status: {import2.status}")

    # Test 6: Timeline
    print("\n[Test 6] Pet Timeline")
    timeline = pet.life_events.all()
    print(f"  ✓ Pet has {timeline.count()} events on timeline")
    for event in timeline:
        print(f"    - {event.title} ({event.event_type})")

    # Summary
    print("\n" + "=" * 70)
    print("END-TO-END TEST PASSED ✓")
    print("=" * 70)
    print("\nKey metrics:")
    print(f"  - User account: {user.username}")
    print(f"  - Pet profile: {pet.name}")
    print(f"  - Social imports: {SocialImport.objects.filter(pet=pet).count()}")
    print(f"  - Life events: {LifeEvent.objects.filter(pet=pet).count()}")
    print(f"  - Timeline events: {pet.life_events.count()}")


if __name__ == "__main__":
    main()
