"""
Seed 20 pravih knjiga za demo — s naslovnicama iz OpenLibrary.
Pokreni: python manage.py shell < library_seed.py
"""
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from companies.models import Company
from library.models import Author, Book, BookCopy, Category, MembershipType

# Uzmi prvu firmu za demo (ili kreiraj)
company = Company.objects.first()
if not company:
    print("GRESKA: Nema firmi u bazi!")
    sys.exit(1)

print(f"Seeding za: {company.name}")

# Kategorije
cats = {}
for name, icon in [
    ("Beletristika", "bi-book"),
    ("Djecja literatura", "bi-emoji-smile"),
    ("Znanost", "bi-lightbulb"),
    ("Povijest", "bi-clock-history"),
    ("Poezija", "bi-feather"),
    ("Filozofija", "bi-yin-yang"),
    ("Kriminalisticki roman", "bi-search"),
    ("Biografija", "bi-person"),
]:
    cat, _ = Category.objects.get_or_create(company=company, name=name, defaults={"icon": icon})
    cats[name] = cat
print(f"  {len(cats)} kategorija")

# Membership types
for name, max_b, days, fee in [
    ("Djeca (do 14)", 5, 21, 0),
    ("Odrasli", 5, 21, 2),
    ("Studenti", 7, 28, 1),
    ("Umirovljenici", 5, 28, 0),
]:
    MembershipType.objects.get_or_create(company=company, name=name, defaults={
        "max_books": max_b, "loan_days": days, "annual_fee": fee,
    })
print("  4 tipa clanarine")

# Knjige
BOOKS = [
    {"title":"Na Drini cuprija","author":"Ivo Andric","isbn":"9789531410380","year":1945,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9789531410380-M.jpg","publisher":"Znanje"},
    {"title":"Prokleta avlija","author":"Ivo Andric","isbn":"9789533040509","year":1954,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9789533040509-M.jpg","publisher":"Skolska knjiga"},
    {"title":"Povratak Filipa Latinovicza","author":"Miroslav Krleza","isbn":"9789530600461","year":1932,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9789530600461-M.jpg","publisher":"Zora"},
    {"title":"Mali princ","author":"Antoine de Saint-Exupery","isbn":"9789532851526","year":1943,"cat":"Djecja literatura","cover":"https://covers.openlibrary.org/b/isbn/9780156012195-M.jpg","publisher":"Mozaik knjiga"},
    {"title":"Harry Potter i Kamen mudraca","author":"J.K. Rowling","isbn":"9789532856415","year":1997,"cat":"Djecja literatura","cover":"https://covers.openlibrary.org/b/isbn/9780747532699-M.jpg","publisher":"Algoritam"},
    {"title":"Vlak u snijegu","author":"Mato Lovrak","isbn":"9789531731232","year":1933,"cat":"Djecja literatura","cover":"https://covers.openlibrary.org/b/isbn/9789531731232-M.jpg","publisher":"Skolska knjiga"},
    {"title":"Sapiens: Kratka povijest covjecanstva","author":"Yuval Noah Harari","isbn":"9789532661682","year":2011,"cat":"Znanost","cover":"https://covers.openlibrary.org/b/isbn/9780062316097-M.jpg","publisher":"Fokus"},
    {"title":"Kratka povijest vremena","author":"Stephen Hawking","isbn":"9789532660128","year":1988,"cat":"Znanost","cover":"https://covers.openlibrary.org/b/isbn/9780553380163-M.jpg","publisher":"Izvori"},
    {"title":"1984","author":"George Orwell","isbn":"9789532661019","year":1949,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9780451524935-M.jpg","publisher":"Alfa"},
    {"title":"Zlocin i kazna","author":"Fjodor Dostojevski","isbn":"9789531410274","year":1866,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9780486415871-M.jpg","publisher":"Globus media"},
    {"title":"Sto godina samoce","author":"Gabriel Garcia Marquez","isbn":"9789532660685","year":1967,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9780060883287-M.jpg","publisher":"VBZ"},
    {"title":"Alisa u Zemlji cudesa","author":"Lewis Carroll","isbn":"9789532854091","year":1865,"cat":"Djecja literatura","cover":"https://covers.openlibrary.org/b/isbn/9780141439761-M.jpg","publisher":"Mozaik knjiga"},
    {"title":"Starac i more","author":"Ernest Hemingway","isbn":"9789532662078","year":1952,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9780684801223-M.jpg","publisher":"Globus media"},
    {"title":"Dnevnik Ane Frank","author":"Ana Frank","isbn":"9789532661347","year":1947,"cat":"Biografija","cover":"https://covers.openlibrary.org/b/isbn/9780553296983-M.jpg","publisher":"Mozaik knjiga"},
    {"title":"Divlja patka","author":"Henrik Ibsen","isbn":"9789531710176","year":1884,"cat":"Beletristika","cover":"","publisher":"AGM"},
    {"title":"Osama bin Laden","author":"Ivana Bodrozic","isbn":"9789532661644","year":2013,"cat":"Beletristika","cover":"","publisher":"Profil"},
    {"title":"Cosmos","author":"Carl Sagan","isbn":"9780345539434","year":1980,"cat":"Znanost","cover":"https://covers.openlibrary.org/b/isbn/9780345539434-M.jpg","publisher":"Ballantine Books"},
    {"title":"Braca Karamazovi","author":"Fjodor Dostojevski","isbn":"9789531410267","year":1880,"cat":"Beletristika","cover":"https://covers.openlibrary.org/b/isbn/9780374528379-M.jpg","publisher":"Globus media"},
    {"title":"Crni macak","author":"Edgar Allan Poe","isbn":"","year":1843,"cat":"Kriminalisticki roman","cover":"","publisher":""},
    {"title":"Hobbit","author":"J.R.R. Tolkien","isbn":"9789532856170","year":1937,"cat":"Djecja literatura","cover":"https://covers.openlibrary.org/b/isbn/9780547928227-M.jpg","publisher":"Algoritam"},
]

created = 0
for b in BOOKS:
    if Book.objects.filter(company=company, title=b["title"]).exists():
        continue
    parts = b["author"].split(" ", 1)
    fname = parts[0]
    lname = parts[1] if len(parts) > 1 else ""
    author, _ = Author.objects.get_or_create(company=company, first_name=fname, last_name=lname)

    isbn = b["isbn"].replace("-", "")
    book = Book.objects.create(
        company=company,
        title=b["title"],
        isbn_13=isbn if len(isbn) == 13 else "",
        publisher=b["publisher"],
        publish_year=b["year"],
        language="hr",
        category=cats.get(b["cat"]),
        cover_url=b["cover"],
    )
    book.authors.add(author)

    # 2 primjerka po knjizi
    for i in range(1, 3):
        barcode = f"LIB-{book.pk:04d}-{i:02d}"
        BookCopy.objects.create(
            book=book, barcode=barcode, status="available",
            location=f"Polica {chr(64 + (book.pk % 5) + 1)}{(book.pk % 10) + 1}",
        )
    created += 1

print(f"  {created} knjiga kreirano (sa po 2 primjerka)")
print("DONE!")
