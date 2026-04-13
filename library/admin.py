from django.contrib import admin
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Author, Category, Book, BookCopy, MembershipType,
    LibraryMember, Loan, Reservation, ImportBatch,
    DigitalAsset, DigitalLoan,
)


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 1


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "birth_year", "death_year"]
    search_fields = ["first_name", "last_name"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "udk_code"]
    list_filter = ["company"]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "isbn_13", "publisher", "publish_year", "times_borrowed"]
    list_filter = ["company", "language", "category"]
    search_fields = ["title", "isbn_13", "isbn_10"]
    inlines = [BookCopyInline]


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ["barcode", "book", "status", "condition", "location"]
    list_filter = ["status", "condition"]
    search_fields = ["barcode", "book__title"]


@admin.register(MembershipType)
class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "max_books", "loan_days", "annual_fee"]


@admin.register(LibraryMember)
class LibraryMemberAdmin(admin.ModelAdmin):
    list_display = ["member_number", "first_name", "last_name", "status", "active_loans_count"]
    list_filter = ["status", "membership_type"]
    search_fields = ["first_name", "last_name", "member_number", "oib"]


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ["member", "copy", "borrowed_date", "due_date", "returned_date", "status"]
    list_filter = ["status"]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ["member", "book", "reserved_date", "status"]
    list_filter = ["status"]


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ["file_name", "status", "total_rows", "books_created", "uploaded_at"]
    list_filter = ["status"]


@admin.register(DigitalAsset)
class DigitalAssetAdmin(admin.ModelAdmin):
    list_display = ["book", "format", "source", "is_active", "max_concurrent_loans"]
    list_filter = ["format", "source", "is_active"]


@admin.register(DigitalLoan)
class DigitalLoanAdmin(admin.ModelAdmin):
    list_display = ["member", "asset", "borrowed_date", "due_date", "returned_date"]


from .models import ReaderProfile

@admin.register(ReaderProfile)
class ReaderProfileAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'parent', 'age_group', 'books_read', 'xp_points', 'parental_consent']
    list_filter = ['age_group', 'reading_level', 'parental_consent']
    search_fields = ['first_name', 'last_name']
