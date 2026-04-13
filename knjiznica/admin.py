from django.contrib import admin

from .models import (
    BadgeDefinition,
    BookLoan,
    BookMeta,
    BookReservation,
    ChildReader,
    EarnedBadge,
    FamilyChallenge,
    LibraryMember,
    MediaContent,
    ReadingLog,
)


@admin.register(BookMeta)
class BookMetaAdmin(admin.ModelAdmin):
    list_display = ('item', 'author', 'isbn', 'age_tier', 'genre', 'shelf_location', 'is_reference')
    search_fields = ('item__name', 'author', 'isbn')
    list_filter = ('is_reference', 'age_tier', 'genre')


@admin.register(LibraryMember)
class LibraryMemberAdmin(admin.ModelAdmin):
    list_display = ('partner', 'member_number', 'status', 'membership_until', 'portal_pin', 'company')
    list_filter = ('status', 'company')
    search_fields = ('partner__name', 'member_number')


@admin.register(BookLoan)
class BookLoanAdmin(admin.ModelAdmin):
    list_display = ('member', 'item', 'status', 'loan_date', 'due_date', 'fine_total')
    list_filter = ('status', 'company')
    search_fields = ('member__partner__name', 'item__name')


@admin.register(BookReservation)
class BookReservationAdmin(admin.ModelAdmin):
    list_display = ('member', 'item', 'status', 'reserved_at')
    list_filter = ('status', 'company')


@admin.register(ChildReader)
class ChildReaderAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'parent', 'tier', 'books_read', 'total_points', 'company')
    list_filter = ('tier', 'company')
    search_fields = ('first_name', 'parent__partner__name')


@admin.register(BadgeDefinition)
class BadgeDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'required_books', 'required_genre', 'is_active', 'sort_order')
    list_filter = ('category', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(EarnedBadge)
class EarnedBadgeAdmin(admin.ModelAdmin):
    list_display = ('child', 'badge', 'earned_at')
    list_filter = ('badge',)


@admin.register(ReadingLog)
class ReadingLogAdmin(admin.ModelAdmin):
    list_display = ('child', 'book_title', 'read_date', 'rating', 'points_earned')
    list_filter = ('company',)
    search_fields = ('child__first_name',)


@admin.register(MediaContent)
class MediaContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'tier', 'is_published', 'view_count', 'company')
    list_filter = ('content_type', 'tier', 'is_published', 'company')
    search_fields = ('title',)


@admin.register(FamilyChallenge)
class FamilyChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'parent', 'challenge_type', 'status', 'progress', 'target_books')
    list_filter = ('status', 'challenge_type', 'company')
