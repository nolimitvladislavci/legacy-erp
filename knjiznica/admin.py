from django.contrib import admin
from .models import BookMeta, LibraryMember, BookLoan, BookReservation


@admin.register(BookMeta)
class BookMetaAdmin(admin.ModelAdmin):
    list_display = ('item', 'author', 'isbn', 'shelf_location', 'is_reference')
    search_fields = ('item__name', 'author', 'isbn')
    list_filter = ('is_reference',)


@admin.register(LibraryMember)
class LibraryMemberAdmin(admin.ModelAdmin):
    list_display = ('partner', 'member_number', 'status', 'membership_until', 'company')
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
