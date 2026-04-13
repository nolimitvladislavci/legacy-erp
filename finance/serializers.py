from rest_framework import serializers
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
