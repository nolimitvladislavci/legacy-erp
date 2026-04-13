from rest_framework import serializers

from .models import *


class InsurancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = InsurancePolicy
        fields = "__all__"
