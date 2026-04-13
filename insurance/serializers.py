from rest_framework import serializers
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from .models import *


class InsurancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePolicy
        fields = '__all__'
