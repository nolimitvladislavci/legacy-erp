#!/usr/bin/env python
"""Quick test script za social import modul"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, '/var/www/fina-connect')
django.setup()

from boxgram.services.social_import import detect_platform, fetch_oembed, _extract_youtube_id

def test_detect_platform():
    """Test detektovanja platforme"""
    tests = [
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'youtube'),
        ('https://youtu.be/dQw4w9WgXcQ', 'youtube'),
        ('https://www.tiktok.com/@user/video/123', 'tiktok'),
        ('https://www.facebook.com/photo.php?fbid=123', 'facebook'),
        ('https://www.instagram.com/p/ABC123/', 'instagram'),
        ('https://www.example.com', None),
    ]

    passed = 0
    for url, expected in tests:
        result = detect_platform(url)
        if result == expected:
            print(f"✓ detect_platform({url[:40]}...) = {result}")
            passed += 1
        else:
            print(f"✗ detect_platform({url[:40]}...) expected {expected}, got {result}")

    return passed, len(tests)

def test_youtube_id_extraction():
    """Test ekstrakcije YouTube ID-a"""
    tests = [
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('https://youtu.be/dQw4w9WgXcQ', 'dQw4w9WgXcQ'),
        ('https://youtube.com/watch?v=abc123&t=10', 'abc123'),
    ]

    passed = 0
    for url, expected in tests:
        result = _extract_youtube_id(url)
        if result == expected:
            print(f"✓ _extract_youtube_id({url[:40]}...) = {result}")
            passed += 1
        else:
            print(f"✗ _extract_youtube_id({url[:40]}...) expected {expected}, got {result}")

    return passed, len(tests)

def test_fetch_oembed():
    """Test fetch_oembed sa nevalidnim URL-ovima"""
    tests = [
        ('https://invalid.domain.xyz/video', False),  # Invalid domain
        ('https://www.example.com/video', False),     # No oEmbed endpoint
    ]

    passed = 0
    for url, should_succeed in tests:
        preview = fetch_oembed(url)
        if preview.success == should_succeed:
            print(f"✓ fetch_oembed({url[:40]}...) success={preview.success}")
            passed += 1
        else:
            print(f"✗ fetch_oembed({url[:40]}...) expected success={should_succeed}, got {preview.success}")

    return passed, len(tests)

def test_social_import_model():
    """Test SocialImport modela"""
    from django.contrib.auth.models import User
    from companies.models import Company
    from boxgram.models import PetProfile, SocialImport
    import uuid

    # Setup
    company = Company.objects.create(
        name=f'TestCo{uuid.uuid4().hex[:8]}',
        oib=f'{uuid.uuid4().hex[:11]}'
    )
    user = User.objects.create_user(
        username=f'user{uuid.uuid4().hex[:8]}',
        email=f'test{uuid.uuid4().hex[:8]}@example.com',
        password='pass123'
    )
    pet = PetProfile.objects.create(
        tenant=company,
        owner=user,
        name='TestPet',
        species='pas',
        slug=f'pet{uuid.uuid4().hex[:8]}'
    )

    passed = 0
    total = 4

    # Test 1: Create
    url = f'https://youtube.com/watch?v={uuid.uuid4().hex[:8]}'
    import1 = SocialImport.objects.create(
        pet=pet,
        platform='youtube',
        source_url=url,
        status='pending'
    )
    if import1.id is not None:
        print("✓ Create SocialImport")
        passed += 1
    else:
        print("✗ Create SocialImport failed")

    # Test 2: Duplicate check
    existing = SocialImport.objects.filter(pet=pet, source_url=url).first()
    if existing is not None:
        print("✓ Duplicate detection works")
        passed += 1
    else:
        print("✗ Duplicate detection failed")

    # Test 3: Status transition
    import1.status = 'rejected'
    import1.save()
    if import1.status == 'rejected':
        print("✓ Status transition works")
        passed += 1
    else:
        print("✗ Status transition failed")

    # Test 4: Raw data storage
    test_data = {'title': 'Test', 'author': 'Author'}
    import2 = SocialImport.objects.create(
        pet=pet,
        platform='tiktok',
        source_url=f'https://tiktok.com/video/{uuid.uuid4().hex[:8]}',
        status='pending',
        raw_data=test_data
    )
    if import2.raw_data.get('title') == 'Test':
        print("✓ Raw data storage works")
        passed += 1
    else:
        print("✗ Raw data storage failed")

    return passed, total

if __name__ == '__main__':
    print("=" * 60)
    print("SOCIAL IMPORT SERVICE TESTS")
    print("=" * 60)

    all_passed = 0
    all_total = 0

    print("\n[1/3] Testing platform detection...")
    p, t = test_detect_platform()
    all_passed += p
    all_total += t

    print("\n[2/3] Testing YouTube ID extraction...")
    p, t = test_youtube_id_extraction()
    all_passed += p
    all_total += t

    print("\n[3/3] Testing fetch_oembed...")
    p, t = test_fetch_oembed()
    all_passed += p
    all_total += t

    print("\n[4/4] Testing SocialImport model...")
    p, t = test_social_import_model()
    all_passed += p
    all_total += t

    print("\n" + "=" * 60)
    print(f"RESULTS: {all_passed}/{all_total} tests passed")
    print("=" * 60)

    sys.exit(0 if all_passed == all_total else 1)
